import bpy
import os

from mathutils import Vector, Quaternion, Matrix, Euler

from .bml import *

from pathlib import Path

def BlenderImport(filepath):
    meshes, materials, bone_nodes, mtxp_section, draws, tex_names = ParseMeshes(filepath)

    name = os.path.splitext(os.path.basename(filepath))[0].rsplit("_", 1)[0]

    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    
    scene = bpy.context.scene

    
    # Node Armature
    node_SkeletonName = "NodeSkeleton"

    node_arm_data = bpy.data.armatures.new(node_SkeletonName)
    node_arm_object = bpy.data.objects.new(node_SkeletonName, node_arm_data)

    collection.objects.link(node_arm_object)

    bpy.context.view_layer.objects.active = node_arm_object
    node_arm_object.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
   
    # Create bone
    node_edit_bones = []
    node_bone_names = []
    
    for bone in bone_nodes:
        bone_name = bone["BoneName"]
        node_bone_names.append(bone_name)
                
        edit_bone = node_arm_data.edit_bones.new(bone_name)
        
        node_edit_bones.append( {"bone_name": bone_name, "bone": edit_bone} )
        
        
    node_world_matrices = {}
    for i, bone in enumerate(node_edit_bones):
        parent_name = bone_nodes[i]["ParentName"]
        
        edit_bone = bone["bone"]
        
        edit_bone_name = bone["bone_name"]
        
        if parent_name != "": # Not root
            parent_bone = next(bone for bone in node_edit_bones if bone["bone_name"] == parent_name)
            
            parent = parent_bone["bone"]
            
            edit_bone.parent = parent
        
        
        
        # Position
        position = bone_nodes[i]["BonePositions"]      
        
        position = Vector(position)
        
        # Rotation
        rotation = bone_nodes[i]["BoneRotation"]
        
        # Scale
        scale = bone_nodes[i]["BoneScale"]
        
        scale = Vector(scale)
        
        # Construct Local and World Bone Matrix
        local_bone_matrix = Matrix.LocRotScale(
            position,
            Euler((rotation[0], rotation[1], rotation[2]), 'XYZ'),
            scale
        )
        
        if parent_name == "":
            world_matrix = local_bone_matrix
            
        else:
            parent_matrix = node_world_matrices[parent_name]
            world_matrix = parent_matrix @ local_bone_matrix

        node_world_matrices[edit_bone_name] = world_matrix
        
        # Assign a Head and Tail to the Edit Bone
        edit_bone.head = Vector((0, 0, 0))
        edit_bone.tail = Vector((0, 1, 0))
        
        # Assign the World Bone Matrix to the Edit Bone
        edit_bone.matrix = node_world_matrices[edit_bone_name]
        
        
        

    bpy.ops.object.mode_set(mode='OBJECT')
    
    
    # Mtxp Armature
    mtxp_SkeletonName = "MtxpSkeleton"

    mtxp_arm_data = bpy.data.armatures.new(mtxp_SkeletonName)
    mtxp_arm_object = bpy.data.objects.new(mtxp_SkeletonName, mtxp_arm_data)

    collection.objects.link(mtxp_arm_object)

    bpy.context.view_layer.objects.active = mtxp_arm_object
    mtxp_arm_object.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
   
    # Create bone
    mtxp_edit_bones = []
    mtxp_bone_names = []
    
    for i in range(mtxp_section.bone_count):
        bone_name = f"bone_{i}"
                
        edit_bone = mtxp_arm_data.edit_bones.new(bone_name)
        
        mtxp_edit_bones.append( {"bone_name": bone_name, "bone": edit_bone} )
        
        
    world_matrices = {}
    for i, (matrix_floats, node_index) in enumerate( zip(mtxp_section.matrices_floats, mtxp_section.node_indices) ):
        blender_matrix = Matrix( (matrix_floats[0:4], matrix_floats[4:8], matrix_floats[8:12], matrix_floats[12:16]) ).transposed().inverted()
        
        edit_bone = mtxp_edit_bones[i]["bone"]
        
        edit_bone.head = Vector((0, 0, 0))
        edit_bone.tail = Vector((0, 0.1, 0))
        
        edit_bone.matrix = blender_matrix
        
        edit_bone.name = node_edit_bones[node_index]["bone_name"]      
        mtxp_bone_names.append(edit_bone.name)
        
    
    # Assign Parents
    for i, node_index in enumerate(mtxp_section.node_indices):
        node_edit_bone_name = node_edit_bones[node_index]["bone_name"]
        parent = node_arm_data.edit_bones.get(node_edit_bone_name).parent

        if parent:
            mtxp_edit_bones[i]["bone"].parent = mtxp_arm_data.edit_bones.get(parent.name)
        

    bpy.ops.object.mode_set(mode='OBJECT')
    
    corresponding_draw = None
    for i, mesh_data in enumerate(meshes):
        for draw in draws:
            if i == draw["MeshIndex"]:
                corresponding_draw = draw
                
        # Choose which LODs to process
        if scene.import_lods:
            lods = mesh_data
        else:
            lods = mesh_data[:1] # LOD0 only
            
        material_index = corresponding_draw["MaterialIndex"]
        if i < len(materials):
            material_name = materials[material_index]["MaterialName"]
            texture_name = materials[material_index]["TextureName"]
            
            p = Path(texture_name)
            texture_name = p.stem + "_tex" + ".png" # e.g.: "c001_tex_a_re_tex.png"
            
            material = bpy.data.materials.new(name=material_name) # Use name of material with index i (indexing of meshes not lods)
            material.use_nodes = True
            
            nodes = material.node_tree.nodes
            links = material.node_tree.links
            
            texture_path = os.path.join(Path(filepath).parent, texture_name) # String
            
            texture_Path = Path(texture_path) # Path object
            
            if texture_Path.exists():
                image = bpy.data.images.load(texture_path)
                image.name = texture_name
               
                tex = nodes.new("ShaderNodeTexImage")
                tex.image = image

                principled = nodes.get("Principled BSDF")

                links.new(
                    tex.outputs["Color"],
                    principled.inputs["Base Color"]
            )


                
                
        
        for j, lod in enumerate(lods):

            mesh = bpy.data.meshes.new(lod.Name if lod.Name else f"{lods[0].Name}_LOD_{j}")
            obj = bpy.data.objects.new(lod.Name if lod.Name else f"{lods[0].Name}_LOD_{j}", mesh)
            collection.objects.link(obj)
            
            mesh.materials.append(material)
            
            
            for tex_name in tex_names:
                item = obj.texture_names.add()
                item.name = tex_name
        
        
            lod_vertices = lod.Vertices
            lod_indices = lod.Indices
            
            
            # -------------------------
            # Positions
            # -------------------------

            positions = [
                tuple(vertex["positions"])
                for vertex in lod_vertices
            ]

            # -------------------------
            # Indices
            # -------------------------

            indices = [
                index
                for index in lod_indices
            ]
            
            if scene.reverse_winding_order:
                faces = [
                    [indices[j], indices[j+2], indices[j+1]]
                    for j in range(0, len(indices), 3)
                ]
                
            else:
                faces = [
                    [indices[j], indices[j+1], indices[j+2]]
                    for j in range(0, len(indices), 3)
                ]

            mesh.from_pydata(positions, [], faces)
            mesh.update()

            # -------------------------
            # Normals
            # -------------------------

            attr = mesh.attributes.get("custom_normal")
            if attr is None:
                    attr = mesh.attributes.new("custom_normal", 'FLOAT_VECTOR', 'POINT')
            
            normals = [tuple(vertex["normals"][:3]) for vertex in lod.Vertices] # Flip direction of vertex normals to match reversing face winding order
            
            for i, normal in enumerate(normals):
                attr.data[i].vector = Vector(normal)

            # -------------------------
            # UVs
            # -------------------------
            
            
            
            uv_layer = mesh.uv_layers.new(name="UVMap")
            
            
            
            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    vertex_index = mesh.loops[loop_index].vertex_index

                    uv = lod_vertices[vertex_index]["texcoords"]
                    
                    if scene.flip_uv_v_axis:
                        uv_layer.data[loop_index].uv = (
                            uv[0],
                            1 - uv[1]
                        )
                        
                    else:
                        uv_layer.data[loop_index].uv = (
                            uv[0],
                            uv[1]
                        )

            # -------------------------
            # Vertex Colors
            # -------------------------

            color_attribute = mesh.color_attributes.new(
                name="Color",
                type='FLOAT_COLOR',
                domain='CORNER'
            )

            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    vertex_index = mesh.loops[loop_index].vertex_index

                    color = lod_vertices[vertex_index]["colors"]

                    color_attribute.data[loop_index].color = (
                        color[0],
                        color[1],
                        color[2],
                        color[3]
                    )
   
   
   
   
            # -------------------------
            # Blendweights and Blendindices
            # -------------------------

            obj.parent = mtxp_arm_object

            # Armature modifier
            modifier = obj.modifiers.new(
                name="Armature",
                type='ARMATURE'
            )

            modifier.object = mtxp_arm_object
            
            used_bone_indices = set()

            # Find only bones that have an actual weight
            for vertex in lod_vertices:
                for bone_index, weight in zip(
                    vertex["blendindices"],
                    vertex["blendweights"]
                ):
                    if weight > 0:
                        used_bone_indices.add(bone_index)

            # Create only the groups that this mesh actually uses
            for bone_index in used_bone_indices:
                bone_name = mtxp_bone_names[bone_index]
                obj.vertex_groups.new(name=bone_name)

            # Assign weights
            for vertex_index, vertex in enumerate(lod_vertices):
                for bone_index, weight in zip(
                    vertex["blendindices"],
                    vertex["blendweights"]
                ):
                    if weight > 0:
                        bone_name = mtxp_bone_names[bone_index]

                        obj.vertex_groups[bone_name].add(
                            [vertex_index],
                            weight,
                            'REPLACE'
                        )
          
          
            mesh.update()
            
            
            
            
           
    
            
            
            