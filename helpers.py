import struct
import bpy
import mathutils
import bmesh

def read_uint8(f, endianness):
    return struct.unpack(endianness + "B", f.read(1))[0]


def read_int8(f, endianness):
    return struct.unpack(endianness + "b", f.read(1))[0]


def read_ushort(f, endianness):
    return struct.unpack(endianness + "H", f.read(2))[0]
    
    
def read_uint(f, endianness):
    return struct.unpack(endianness + "I", f.read(4))[0]
    

def read_uint64(f, endianness):
    return struct.unpack(endianness + "Q", f.read(8))[0]


def read_halffloat(f, endianness):
    return struct.unpack(endianness + "e", f.read(2))[0]
    

def read_float(f, endianness):
    return struct.unpack(endianness + "f", f.read(4))[0]
    

def read_cstring(f, encoding="utf-8"):
    chars = bytearray()

    while True:
        b = f.read(1)
        if b == b"" or b == b"\x00":
            break
        chars.extend(b)

    return chars.decode(encoding)
    


def align(num, f, offset):
    if num <= 0:
        raise ValueError(f"Invalid alignment: {num} at offset {offset:#x}")
        
    alignment_bytes = (num - (offset % num)) % num
    f.seek(alignment_bytes, 1)


    

def write_uint8(out, endianness, data):
    return out.write( struct.pack(endianness + "B", data) )


def write_ushort(out, endianness, data):
    return out.write( struct.pack(endianness + "H", data) )
    
    
def write_uint(out, endianness, data):
    return out.write( struct.pack(endianness + "I", data) )


def write_int(out, endianness, data):
    return out.write( struct.pack(endianness + "i", data) )
    

def write_uint64(out, endianness, data):
    return out.write( struct.pack(endianness + "Q", data) )


def write_halffloat(out, endianness, data):
    return out.write( struct.pack(endianness + "e", data) )
    
    
def write_float(out, endianness, data):
    return out.write( struct.pack(endianness + "f", data) )
    

def write_alignment(num, out, offset):
    alignment_bytes = (num - (offset % num)) % num
    out.write(alignment_bytes * b"\x00")


def calculate_hash(string):
    h = 0
    for c in string.encode("ascii"):         
        h = (h * 33 + c) & 0xFFFFFFFF
        
    h = (h + (h >> 5)) & 0xFFFFFFFF

    return h
    
    
def get_used_bones(collection_name):
    collection = bpy.data.collections.get(collection_name)
    if not collection:
        return []

    armature = next(
        (obj for obj in collection.objects if obj.type == 'ARMATURE'),
        None
    )
    if not armature:
        return []

    meshes = [
        obj for obj in collection.objects
        if obj.type == 'MESH'
    ]

    used_bones = set()

    # Find used bones
    for mesh in meshes:
        for vert in mesh.data.vertices:
            for g in vert.groups:
                vg_name = mesh.vertex_groups[g.group].name

                if vg_name in armature.data.bones and g.weight > 0:
                    used_bones.add(vg_name)

    # Preserve vertex-group order
    bone_names = []

    for mesh in meshes:
        for vg in mesh.vertex_groups:
            if vg.name in used_bones and vg.name not in bone_names:
                bone_names.append(vg.name)

    return bone_names
    

def get_used_bones_per_mesh(blend_indices, blend_weights, bone_palette, vert_map):
    used_bones = set()
    
    for global_vert_index in vert_map:
        vertex_blend_indices = blend_indices[global_vert_index]
        vertex_blend_weights = blend_weights[global_vert_index]
        
        for index, weight in zip(vertex_blend_indices, vertex_blend_weights):
            if weight > 0:
                used_bones.add(index)

    return sorted(used_bones)



def attr_or_none(obj, name):
    return getattr(obj, name, None) if obj else None
    
    
    
class BlenderMeshExtractor:
    def __init__(self, obj, armature_obj):
        self.obj = obj
        self.armature_obj = armature_obj

    def ExtractBlenderMeshData(self):

        obj = self.obj
        mesh = obj.to_mesh()
        
        uv_layers = mesh.uv_layers
        color_layers = mesh.color_attributes
        
        # --------------------------------------------------
        # STEP 1: CREATE BMESH
        # --------------------------------------------------
        
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        bmesh.ops.triangulate(bm, faces=bm.faces)
        
        bm.to_mesh(mesh)
        bm.free()
        

        # --------------------------------------------------
        # STEP 3: GET ATTRIBUTE LAYERS
        # --------------------------------------------------
        
        
        mesh_uv_layers = list(mesh.uv_layers)
        mesh_colors_layers = list(mesh.color_attributes)

        
        # --------------------------------------------------
        # STEP 4: OUTPUT BUFFERS
        # --------------------------------------------------
        positions = []
        normals = []
        tangents = []
        binormals = []
        uvs = []
        colors = []
        blend_indices = []
        blend_weights = []
        triangles = []

        # --------------------------------------------------
        # STEP 5: DEDUP MAP
        # --------------------------------------------------
        self.vertex_map = {}

        def vertex_key(pos, uv, normal):
            return (
                tuple(pos),
                

                tuple(uv),
                tuple(normal),
         

            
            )      
        
        # --------------------------------------------------
        # STEP 6: TRIANGLE EXTRACTION
        # --------------------------------------------------
        
        uv_layers = [
            [tuple(layer.data[i].uv) for i in range(len(mesh.loops))]
            for layer in mesh.uv_layers
        ]

        color_layers = [
            [tuple(layer.data[i].color) for i in range(len(mesh.loops))]
            for layer in mesh.color_attributes
        ]
        

        mesh.calc_tangents()
        
        
        # --- Now iterate over triangles ---
        tri_indices = []
        for loop in mesh.loops:
            loop = mesh.loops[loop.index]
            vidx = loop.vertex_index
            v = mesh.vertices[vidx]

            matrix = obj.matrix_world
            rot = matrix.to_3x3().normalized()

            pos = matrix @ v.co # Apply all transforms to positions
            normal = (rot @ loop.normal).normalized() # Apply rotation matrix to normals, after applying scale in Blender
            # No need for inverse-transpose matrix

            # Skinning
            groups = [
                g for g in v.groups
            ]

            groups = sorted(
                groups,
                key=lambda g: g.weight,
                reverse=True
            )[:4]

            bi = []
            bw = []

            for g in groups:
                bone_name = obj.vertex_groups[g.group].name
                
                bone_index = self.armature_obj.data.bones.find(bone_name)
                
                bi.append(bone_index)
                bw.append(g.weight)

            total = sum(bw)

            if total > 0:
                bw = [w / total for w in bw]

            while len(bi) < 4:
                bi.append(0)
                bw.append(0.0)

            # Tangent space
            tangent = (rot @ loop.tangent).normalized()
            
            bitangent_sign = loop.bitangent_sign
            binormal = normal.cross(tangent) * bitangent_sign
            
            vertex_uv = [uv_layers[l][loop.index] for l in range(len(uv_layers))]
            vertex_color = [color_layers[l][loop.index] for l in range(len(color_layers))]

            
            
            
            
            key = vertex_key(pos, vertex_uv, normal)
            
            # Emit vertex
            if key not in self.vertex_map:
                idx = len(positions)
                self.vertex_map[key] = idx

                positions.append(pos.copy())
                normals.append(normal.copy())
                tangents.append(tangent)
                binormals.append(binormal)
                uvs.append(vertex_uv)
                colors.append(vertex_color)
                blend_indices.append(bi)
                blend_weights.append(bw)
            else:
                idx = self.vertex_map[key]
            
            tri_indices.append(idx)
            if len(tri_indices) == 3:
                triangles.append(tri_indices)
                tri_indices = []
        

        obj.to_mesh_clear()
        
        # --------------------------------------------------
        # STEP 8: RETURN EVERYTHING
        # --------------------------------------------------
        return {
            "positions": positions,
            "normals": normals,
            "tangents": tangents,
            "binormals": binormals,
            "uvs": uvs,
            "colors": colors,
            "blend_indices": blend_indices,
            "blend_weights": blend_weights,
            "triangle_list": triangles,
        }
        
        
        
def FetchBlenderData(mesh_objects):
    # =========================
    # 1. HELPERS
    # =========================
    
    
    def get_armature_object(obj):
        # Find the armature object for this mesh
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE':
                return mod.object
        return None
        
    
    def clean_name(name):
        return name.rsplit(".", 1)[0]
        
    def get_material_name(obj):
        mats = obj.data.materials

        if mats and mats[0]:
            return clean_name(mats[0].name)

        return None

    
        
        

    # =========================
    # 2. COLLECT + PROCESS DATA
    # =========================

    mesh_data_list = []
    all_positions = []

    for obj in mesh_objects:
        armature_obj = get_armature_object(obj)
        
        blender_mesh = BlenderMeshExtractor(obj, armature_obj)
        mesh_dict = blender_mesh.ExtractBlenderMeshData()

        positions = mesh_dict["positions"]
        if not positions:
            continue
        
        all_positions.extend(positions)
        
        
        skeleton_name = armature_obj.name if armature_obj else None
        material_name = get_material_name(obj)
        
        mesh_origin = obj.location
        
        mesh_data = {
            "obj": obj,
            "mesh_origin": mesh_origin,
            "mesh": blender_mesh,
            "data": mesh_dict,
            "vertex_count": len(mesh_dict["positions"]),
            "triangles": mesh_dict["triangle_list"],
            "skeleton_name": skeleton_name,
            "material_name": material_name
        }

        mesh_data_list.append(mesh_data)


    from mathutils import Vector

    # =========================
    # 3. MODEL-LEVEL DATA
    # =========================

    min_pos = Vector((
        min(p[0] for p in all_positions),
        min(p[1] for p in all_positions),
        min(p[2] for p in all_positions)
    ))

    max_pos = Vector((
        max(p[0] for p in all_positions),
        max(p[1] for p in all_positions),
        max(p[2] for p in all_positions)
    ))

    sphere_center = (min_pos + max_pos) / 2
    radius = max((Vector(p) - sphere_center).length for p in all_positions)

    # Return all
    return {
        "meshes": mesh_data_list,
        "aabb_min": min_pos,
        "aabb_max": max_pos,
        "sphere_center": sphere_center,
        "sphere_radius": radius,
    }
   
