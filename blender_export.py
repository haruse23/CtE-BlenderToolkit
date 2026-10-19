import bpy
import os

from mathutils import Vector, Quaternion, Matrix, Euler

from .bml import *

from pathlib import Path

from .helpers import *

ENDIANNESS = "<"

import glob

def BlenderExport(collection, filepath, mesh_objects):
    with open(filepath, "wb") as out:
    
        if collection is None:
            raise ValueError("Collection is None!")
        
        base_meshes = [obj for obj in mesh_objects if "LOD" not in obj.name]
        mesh_count = len(base_meshes)
        
        data = FetchBlenderData(mesh_objects)
        
        meshes_data = data["meshes"] # mesh_data_list, List of each mesh data (List of dictionaries for every mesh)
        
        scene = bpy.context.scene
        
        folder = os.path.dirname(filepath)

        tex_files = glob.glob(os.path.join(folder, "**", "*_tex"), recursive=True)
        
        tex_files_names = []
        for tex_file in tex_files:
            tex_files_names.append( os.path.basename(tex_file).rsplit("_tex", 1)[0] )
        
        ###################################################################
        bml_header_start = out.tell()
        
        out.write(b"BML\x00")
        write_uint(out, ENDIANNESS, 16) # 0x10
        write_ushort(out, ENDIANNESS, 0)
        write_ushort(out, ENDIANNESS, 4)
        
        write_ushort(out, ENDIANNESS, mesh_count)
        write_ushort(out, ENDIANNESS, 0) # NodeSkeleton bone count
        
        write_ushort(out, ENDIANNESS, 0) # Material count
        write_ushort(out, ENDIANNESS, 0) # Palette count
        
        write_ushort(out, ENDIANNESS, 0) # DRAW count
        write_ushort(out, ENDIANNESS, 0) # TXTR count
        
        write_ushort(out, ENDIANNESS, 0) # 0
        write_ushort(out, ENDIANNESS, 1) # 1, POF ?
        
        write_alignment(4, out, out.tell())
        
        POF = []
        ###################################################################
        node_skeleton_start = out.tell()
        
        node_skeleton = collection.objects.get("NodeSkeleton")
        
        node_bone_index = {b.name: i for i, b in enumerate(node_skeleton.data.bones)}
        
        bml_starts = []
        bml_sizes = []
        
        mesh_bounds = {}
        for node_bone in node_skeleton.data.bones:
            if node_bone.parent:
                local_matrix = (
                    node_bone.parent.matrix_local.inverted()
                    @ node_bone.matrix_local
                )
            else:
                local_matrix = node_bone.matrix_local

            position, rotation, scale = local_matrix.decompose()
            rotation_euler = rotation.to_euler('XYZ')
            
            
            node_object = BMLBoneNodeSection()
            
            node_object.BoneNameOffset = 0
            node_object.ParentNameOffset = 0
            
            node_object.BonePosition = position
            node_object.BoneScale = scale
            node_object.BoneRotation = rotation_euler
            
            node_object.bone_name = node_bone.name
            node_object.parent_index = node_bone_index[node_bone.parent.name] if node_bone.parent else -1
            
            node_object.Write(out, base_meshes, mesh_bounds)
            
            bml_start1 = out.tell()
            bml_object = BMLSection()
            
            bml_object.name = "DATA"
            bml_object.size = 0
            bml_object.unk = 0
            bml_object.alignment_num = 4
            
            bml_object.WriteBMLSection(out)
            
            pos1name1 = out.tell()
            out.write(node_bone.name.encode("ascii") + b"\x00")
            pos2 = out.tell()
            
            write_alignment(4, out, out.tell())
            
            
            size1 = pos2 - pos1name1          
            
            bml_start2 = out.tell()
            bml_object.name = "DATA"
            bml_object.size = 0
            bml_object.unk = 0
            bml_object.alignment_num = 4
            
            bml_object.WriteBMLSection(out)
            
            pos1name2 = out.tell()
            parent_name = node_bone.parent.name.encode("ascii") if node_bone.parent else b"\x00"
            
            if parent_name == b"\x00":
                out.write(parent_name)
                
            else:
                out.write(parent_name + b"\x00")
                
            pos2 = out.tell()
            
            write_alignment(4, out, out.tell())
            
            
            size2 = pos2 - pos1name2
            
            
            bml_starts.append( (pos1name1, pos1name2) )
            bml_sizes.append( (size1, size2) )
            
            POF.append(node_object.pos1)
            POF.append(node_object.pos2)
        
        
        
        ###################################################################
        mat_start = out.tell()
        
        mat_obj = BMLMaterialSection()
        
        mats = []
        
        texs = []
        
        mat_rewrite_data = []
        
        for mesh_object in mesh_objects:
            mat = mesh_object.data.materials[0]
            
            if mat in mats:
                continue
                
            mat_name = mat.name.split(".")[0]
            
            dif_texture = next( (n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None)
            texture_name = dif_texture.name.rsplit(".", 1)[0].rsplit(".", 1)[0].rsplit("_", 1)[0] if dif_texture else "\x00" # e.g.: c001_tex_a_re instead of c001_tex_a_re_tex.png.001
            
            if dif_texture not in texs:
                texs.append(dif_texture)
            
            mat_obj.size, mat_obj.MaterialNameOffset, mat_obj.TextureNameOffset, mat_obj.size_matname_data, mat_obj.size_texturename_data = (0, 0, 0, 0, 0)
            
            mat_obj.MaterialName, mat_obj.TextureName = (mat_name, texture_name)
            
            mat_obj.Write(out)
            
            size_matname_data, size_texturename_data, size_mat = (mat_obj.pos_name2 - mat_obj.pos_name1, mat_obj.pos_name4 - mat_obj.pos_name3, mat_obj.pos0 - mat_obj.pos_mat_start)
            
            mats.append(mat)
            
            mat_rewrite_data.append( (size_matname_data, size_texturename_data, size_mat, mat_obj.pos_name1, mat_obj.pos_name3) )
            
            POF.append(mat_obj.pos1)
            POF.append(mat_obj.pos2)
            
        ###################################################################    
        mesh_start = out.tell()
        
        mesh_obj = BMLMeshSection()
        vertex = Vertex()
        index = Index()
        
        vert_start, index_start = (0, 0)
        
        mesh_rewrite_data = []
        
        mesh_lods_pos = {}
        base_ptr_pos = {}
        
        mesh_bounds = {}
        for i, mesh_object in enumerate(mesh_objects):     
            mesh_data_dict = meshes_data[i]["data"]
            triangles = meshes_data[i]["triangles"]
            
            blend_weights_1 = [ [0, 0, 0, 0] for i in range( len(mesh_data_dict["blend_weights"]) )]
            blend_indices_1 = [ [0, 0, 0, 0] for i in range( len(mesh_data_dict["blend_indices"]) )]
            
            if scene.flip_uv_v_axis:
                mesh_data_dict["uvs"] = [
                    [(u, 1.0 - v) for u, v in channel]
                    for channel in mesh_data_dict["uvs"]
                ]
            
            # AABB
            positions = mesh_data_dict["positions"]
            min_pos = Vector((
                min(p[0] for p in positions),
                min(p[1] for p in positions),
                min(p[2] for p in positions)
            ))

            max_pos = Vector((
                max(p[0] for p in positions),
                max(p[1] for p in positions),
                max(p[2] for p in positions)
            ))

            # Bounding sphere
            sphere_center = (min_pos + max_pos) / 2
            radius = max((Vector(p) - sphere_center).length for p in positions)
            
            
            vertex_count = meshes_data[i]["vertex_count"]
            index_count = len([index for tri in triangles for index in tri])
            
            vertex_stride = 84
            index_size = 2 if vertex_count < 65535 else 4
            
            
            mesh_obj.MeshNameOffset, mesh_obj.MeshVertexBufferOffset, mesh_obj.MeshIndexBufferOffset, mesh_obj.MeshIndexBufferInfoOffset, mesh_obj.MeshLOD1Offset, mesh_obj.MeshLOD2Offset, mesh_obj.MeshLOD3Offset, mesh_obj.MeshLOD4Offset = (0, 0, 0, 0, 0, 0, 0, 0)
            
            mesh_obj.IndexCount, mesh_obj.VertexCount, mesh_obj.IndexSize, mesh_obj.VertexStride = (index_count, vertex_count, index_size, vertex_stride)
            

                    
            
            from collections import Counter

            lod_counts = Counter(
                obj.name.split("_LOD_")[0]
                for obj in mesh_objects
                if "_LOD_" in obj.name
            )

            if "_LOD_" in mesh_object.name:
                mesh_obj.Write(out, mesh_data_dict["blend_weights"], mesh_object.name, 0)
                
            else:
                mesh_obj.Write(
                    out,
                    mesh_data_dict["blend_weights"],
                    mesh_object.name,
                    lod_counts[mesh_object.name]
                )
            
            is_lod = "_LOD_" in mesh_object.name

            if not is_lod:
                current_base = mesh_object.name
                base_ptr_pos[current_base] = [mesh_obj.pos5, mesh_obj.pos6, mesh_obj.pos7, mesh_obj.pos8]
                mesh_lods_pos[current_base] = {}
                
                mesh_bounds[mesh_object.name] = (min_pos, max_pos, sphere_center, radius)
                
            else:
                lod_index = int(mesh_object.name.split("_LOD_")[1])
                mesh_lods_pos[current_base][lod_index] = mesh_obj.pos1
                POF.append(base_ptr_pos[current_base][lod_index - 1])
               

                    
                    
            if not "LOD" in mesh_object.name:
                out.write("DATA".encode("utf-8"))
                write_uint(out, ENDIANNESS, 0)
                out.write(b"\x00" * 2)
                write_ushort(out, ENDIANNESS, 4) # Alignment_num
                
                pos_name1 = out.tell()
                out.write(mesh_object.name.encode("ascii") + b"\x00")
                pos_name2 = out.tell()
                
                write_alignment(4, out, out.tell())
                
                
                size_DATA1 = pos_name2 - pos_name1
            
           
            vertex.size = 0
            vertex.vertex_count = vertex_count
            vertex.vertices = {"positions": mesh_data_dict["positions"], "blendweights": mesh_data_dict["blend_weights"], "blendindices": mesh_data_dict["blend_indices"], "blendweights_1": blend_weights_1, "blendindices_1": blend_indices_1, "normals": mesh_data_dict["normals"], "colors": mesh_data_dict["colors"], "texcoords": mesh_data_dict["uvs"], "binormals": mesh_data_dict["binormals"], "tangents": mesh_data_dict["tangents"]}
            
            vertex.Write(out)
            
            Vertex_Write_Size = vertex.pos_end - vertex.pos0
            
            # Index Info
            out.write("DATA".encode("utf-8"))
            write_uint(out, ENDIANNESS, 0)
            out.write(b"\x00" * 2)
            write_ushort(out, ENDIANNESS, 4) # Alignment_num
            
            pos_DATA2_0 = out.tell()
            write_uint(out, ENDIANNESS, vertex_count)
            write_uint(out, ENDIANNESS, 0)
            write_uint(out, ENDIANNESS, index_count)
            write_uint(out, ENDIANNESS, 0)
            write_uint(out, ENDIANNESS, 0)
            pos_DATA2_end = out.tell()
            
            write_alignment(4, out, out.tell())
            
            
            
            size_DATA2 = pos_DATA2_end - pos_DATA2_0
            
            
            
            # Index
            index.size = 0
            triangles = meshes_data[i]["triangles"]
            
            if scene.reverse_winding_order:
                triangles = [ (tri[0], tri[2], tri[1]) for tri in triangles ]
                index.Indices = [index for tri in triangles for index in tri]
                
            else:
                index.Indices = [index for tri in triangles for index in tri]
            
            index.Write(out, vertex_count)
            
            Index_Write_Size = index.index_write_end - index.index_write_start
            
            
            if not "LOD" in mesh_object.name:
                POF.append(mesh_obj.pos1)
                
            POF.append(mesh_obj.pos2)
            POF.append(mesh_obj.pos3)
            POF.append(mesh_obj.pos4)
            
            

            
            
            vert_start += vertex_count
            index_start += index_count
            
            mesh_rewrite_data.append( (size_DATA1, size_DATA2, pos_name1, vertex.pos0, index.index_write_start, pos_DATA2_0, Vertex_Write_Size, Index_Write_Size) )
            
        ###################################################################
        mtxp_skeleton_start = out.tell()
        
        mtxp_skeleton = collection.objects.get("MtxpSkeleton")
        
        mtxp_bone_index = {b.name: i for i, b in enumerate(mtxp_skeleton.data.bones)}
        bone_matrices = []
        node_indices = []
        
        mtxp_rewrite_data = []
        
        for mtxp_bone in mtxp_skeleton.data.bones:
            bone_matrix = mtxp_bone.matrix_local.transposed().inverted()
            node_index = node_bone_index[mtxp_bone.name]
            
            bone_matrices.append( bone_matrix )
            
            node_indices.append( node_index )
            
            
        mtxp_object = BMLMtxpSection()
        
        mtxp_object.node_index_list_offset, mtxp_object.matrices_offset = (0, 0)
        
        mtxp_object.bone_count, mtxp_object.matrices_floats, mtxp_object.node_indices = (len(mtxp_skeleton.data.bones), bone_matrices, node_indices)
        
        mtxp_object.Write(out, 0, 0)
        
        mtxp_DATA1_size = mtxp_object.pos1end - mtxp_object.pos01
        mtxp_DATA2_size = mtxp_object.pos2end - mtxp_object.pos02
        
        POF.append(mtxp_object.pos1)
        POF.append(mtxp_object.pos2)
        
        mtxp_rewrite_data.append( (mtxp_DATA1_size, mtxp_DATA2_size, mtxp_object.pos02, mtxp_object.pos01) ) # node_index_list_offset first, then matrices_offset
        ###################################################################
        draw_start = out.tell()
        
        draw_obj = BMLDrawSection()
        
        for i, base_mesh in enumerate(base_meshes):   
            mat = base_mesh.data.materials[0]
  
            if mat in mats:
                draw_obj.node_index = 0
                draw_obj.mesh_index = i
                draw_obj.material_index = mats.index(mat)
                
                draw_obj.Write(out)
                
        ###################################################################
        out.write("MDL\x00".encode("utf-8"))
        write_uint(out, ENDIANNESS, 40)
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        for pos in data["aabb_min"]:
            write_float(out, ENDIANNESS, pos)
            
        for pos in data["aabb_max"]:
            write_float(out, ENDIANNESS, pos)
            
        for pos in data["sphere_center"]:
            write_float(out, ENDIANNESS, pos)
            
        write_float(out, ENDIANNESS, data["sphere_radius"])
        
        
        ###################################################################
        txtr_start = out.tell()
        
        txtr_obj = BMLTxtrSection()
        
        txtr_rewrite_data = []
        
        mesh_obj = bpy.context.active_object

        for i, tex_file_name in enumerate(mesh_obj.texture_names):
            name = tex_file_name.name
            
            txtr_obj.name = name
            txtr_obj.datasize = 0
            txtr_obj.pos_name = 0
            
            txtr_obj.Write(out)
            
            txtr_rewrite_data.append( (txtr_obj.pos1 - txtr_obj.pos0, txtr_obj.pos0) )
        
            POF.append(txtr_obj.posname_pos)
        
        ###################################################################        
        pof_start = out.tell()
        
        out.write("POF0".encode("utf-8"))
        write_uint(out, ENDIANNESS, 0)
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        pof_data_start = out.tell()
        
        write_uint(out, ENDIANNESS, len(POF) + 1)
        
        for pof in POF:
            write_uint(out, ENDIANNESS, pof)
            
        pof_end = out.tell()
        
        pof_size = pof_end - pof_data_start
        
        
        ###################################################################   
        ## Rewriting, fixing offsets
        ###################################################################    
        out.seek(bml_header_start)
        
        out.write(b"BML\x00")
        write_uint(out, ENDIANNESS, 16) # 0x10
        write_ushort(out, ENDIANNESS, 0)
        write_ushort(out, ENDIANNESS, 4)
        
        write_ushort(out, ENDIANNESS, mesh_count)
        write_ushort(out, ENDIANNESS, len(node_skeleton.data.bones)) # NodeSkeleton bone count
        
        write_ushort(out, ENDIANNESS, len(mats)) # Material count
        write_ushort(out, ENDIANNESS, 1) # Palette count
        
        write_ushort(out, ENDIANNESS, mesh_count) # DRAW count
        write_ushort(out, ENDIANNESS, len(mesh_object.texture_names)) # TXTR count
        
        write_ushort(out, ENDIANNESS, 0) # 0
        write_ushort(out, ENDIANNESS, 1) # 1, POF ?
        
        write_alignment(4, out, out.tell())
        
        ###################################################################
        
        out.seek(node_skeleton_start)
        
        node_skeleton = collection.objects.get("NodeSkeleton")
        
        node_bone_index = {b.name: i for i, b in enumerate(node_skeleton.data.bones)}
   
        for i, node_bone in enumerate(node_skeleton.data.bones):
            if node_bone.parent:
                local_matrix = (
                    node_bone.parent.matrix_local.inverted()
                    @ node_bone.matrix_local
                )
            else:
                local_matrix = node_bone.matrix_local

            position, rotation, scale = local_matrix.decompose()
            rotation_euler = rotation.to_euler('XYZ')
            
 
            node_object = BMLBoneNodeSection()
            
            node_object.BoneNameOffset = bml_starts[i][0]
            node_object.ParentNameOffset = bml_starts[i][1]
            
            node_object.BonePosition = position
            node_object.BoneScale = scale
            node_object.BoneRotation = rotation_euler
            
            node_object.bone_name = node_bone.name
            node_object.parent_index = node_bone_index[node_bone.parent.name] if node_bone.parent else -1
            
            node_object.Write(out, base_meshes, mesh_bounds)

            bml_object = BMLSection()
            
            bml_object.name = "DATA"
            bml_object.size = bml_sizes[i][0]
            bml_object.unk = 0
            bml_object.alignment_num = 4
            
            bml_object.WriteBMLSection(out)

            out.write(node_bone.name.encode("ascii") + b"\x00")
            write_alignment(4, out, out.tell())

            

            bml_object.name = "DATA"
            bml_object.size = bml_sizes[i][1]
            bml_object.unk = 0
            bml_object.alignment_num = 4
            
            bml_object.WriteBMLSection(out)

            parent_name = node_bone.parent.name.encode("ascii") if node_bone.parent else b"\x00"
            
            if parent_name == b"\x00":
                out.write(parent_name)
                
            else:
                out.write(parent_name + b"\x00")
                
            write_alignment(4, out, out.tell())

        
        
        ###################################################################
        out.seek(mat_start)
        
        mat_obj = BMLMaterialSection()
        
        for i, mat in enumerate(mats):               
            mat_name = mat.name.split(".")[0]
            
            dif_texture = next( (n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None)
            texture_name = dif_texture.name.rsplit(".", 1)[0].rsplit(".", 1)[0].rsplit("_", 1)[0] if dif_texture else "\x00" # e.g.: c001_tex_a_re instead of c001_tex_a_re_tex.png.001
            
            mat_obj.size, mat_obj.MaterialNameOffset, mat_obj.TextureNameOffset, mat_obj.size_matname_data, mat_obj.size_texturename_data = (mat_rewrite_data[i][2], mat_rewrite_data[i][3], mat_rewrite_data[i][4], mat_rewrite_data[i][0], mat_rewrite_data[i][1])
            
            mat_obj.MaterialName, mat_obj.TextureName = (mat_name, texture_name)
            
            mat_obj.Write(out)

        ###################################################################    
        out.seek(mesh_start)
        
        mesh_obj = BMLMeshSection()
        vertex = Vertex()
        index = Index()
        
        vert_start, index_start = (0, 0)
        
        for i, mesh_object in enumerate(mesh_objects):
            mesh_data_dict = meshes_data[i]["data"]
            triangles = meshes_data[i]["triangles"]
            
            blend_weights_1 = [ [0, 0, 0, 0] for i in range( len(mesh_data_dict["blend_weights"]) )]
            blend_indices_1 = [ [0, 0, 0, 0] for i in range( len(mesh_data_dict["blend_indices"]) )]
            
            
            
            vertex_count = meshes_data[i]["vertex_count"]
            index_count = len([index for tri in triangles for index in tri])
            
            vertex_stride = 84
            index_size = 2 if vertex_count < 65535 else 4
            
            
            
            if not "LOD" in mesh_object.name:
                if mesh_lods_pos[mesh_object.name]:
                    mesh_obj.MeshNameOffset, mesh_obj.MeshVertexBufferOffset, mesh_obj.MeshIndexBufferOffset, mesh_obj.MeshIndexBufferInfoOffset, mesh_obj.MeshLOD1Offset, mesh_obj.MeshLOD2Offset, mesh_obj.MeshLOD3Offset, mesh_obj.MeshLOD4Offset = (mesh_rewrite_data[i][2], mesh_rewrite_data[i][3], mesh_rewrite_data[i][4], mesh_rewrite_data[i][5], mesh_lods_pos[mesh_object.name][1], mesh_lods_pos[mesh_object.name][2], mesh_lods_pos[mesh_object.name][3], mesh_lods_pos[mesh_object.name][4])
                    
                else:
                    mesh_obj.MeshNameOffset, mesh_obj.MeshVertexBufferOffset, mesh_obj.MeshIndexBufferOffset, mesh_obj.MeshIndexBufferInfoOffset, mesh_obj.MeshLOD1Offset, mesh_obj.MeshLOD2Offset, mesh_obj.MeshLOD3Offset, mesh_obj.MeshLOD4Offset = (mesh_rewrite_data[i][2], mesh_rewrite_data[i][3], mesh_rewrite_data[i][4], mesh_rewrite_data[i][5], 0, 0, 0, 0)
                    
            else:
                base_name = mesh_object.name.split("_LOD_")[0]
                mesh_obj.MeshNameOffset, mesh_obj.MeshVertexBufferOffset, mesh_obj.MeshIndexBufferOffset, mesh_obj.MeshIndexBufferInfoOffset, mesh_obj.MeshLOD1Offset, mesh_obj.MeshLOD2Offset, mesh_obj.MeshLOD3Offset, mesh_obj.MeshLOD4Offset = (0, mesh_rewrite_data[i][3], mesh_rewrite_data[i][4], mesh_rewrite_data[i][5], 0, 0, 0, 0)
                
                
                
            mesh_obj.IndexCount, mesh_obj.VertexCount, mesh_obj.IndexSize, mesh_obj.VertexStride = (index_count, vertex_count, index_size, vertex_stride)
            
            from collections import Counter

            lod_counts = Counter(
                obj.name.split("_LOD_")[0]
                for obj in mesh_objects
                if "_LOD_" in obj.name
            )

            if "_LOD_" in mesh_object.name:
                mesh_obj.Write(out, mesh_data_dict["blend_weights"], mesh_object.name, 0)
                
            else:
                mesh_obj.Write(
                    out,
                    mesh_data_dict["blend_weights"],
                    mesh_object.name,
                    lod_counts[mesh_object.name]
                )
            
            if not "LOD" in mesh_object.name:
                out.write("DATA".encode("utf-8"))
                write_uint(out, ENDIANNESS, mesh_rewrite_data[i][0])
                out.write(b"\x00" * 2)
                write_ushort(out, ENDIANNESS, 4) # Alignment_num
                
                
                out.write(mesh_object.name.encode("ascii") + b"\x00")
                
                write_alignment(4, out, out.tell())

            vertex.size = mesh_rewrite_data[i][6]
            vertex.vertex_count = vertex_count
            vertex.vertices = {"positions": mesh_data_dict["positions"], "blendweights": mesh_data_dict["blend_weights"], "blendindices": mesh_data_dict["blend_indices"], "blendweights_1": blend_weights_1, "blendindices_1": blend_indices_1, "normals": mesh_data_dict["normals"], "colors": mesh_data_dict["colors"], "texcoords": mesh_data_dict["uvs"], "binormals": mesh_data_dict["binormals"], "tangents": mesh_data_dict["tangents"]}
            
            vertex.Write(out)
            
            
            
            # Index Info
            out.write("DATA".encode("utf-8"))
            write_uint(out, ENDIANNESS, mesh_rewrite_data[i][1])
            out.write(b"\x00" * 2)
            write_ushort(out, ENDIANNESS, 4) # Alignment_num
            
            write_uint(out, ENDIANNESS, vertex_count)
            write_uint(out, ENDIANNESS, 0)
            write_uint(out, ENDIANNESS, index_count)
            write_uint(out, ENDIANNESS, 0)
            write_uint(out, ENDIANNESS, 0)
            
            write_alignment(4, out, out.tell())

            
            # Index
            index.size = mesh_rewrite_data[i][7]
            triangles = meshes_data[i]["triangles"]
            
            if scene.reverse_winding_order:
                triangles = [ (tri[0], tri[2], tri[1]) for tri in triangles ]
                index.Indices = [index for tri in triangles for index in tri]
                
            else:
                index.Indices = [index for tri in triangles for index in tri]
            
            index.Write(out, vertex_count)
            
 

            
            vert_start += vertex_count
            index_start += index_count
        
            
        ###################################################################
        out.seek(mtxp_skeleton_start)
        
        mtxp_skeleton = collection.objects.get("MtxpSkeleton")
        
        mtxp_bone_index = {b.name: i for i, b in enumerate(mtxp_skeleton.data.bones)}
        bone_matrices = []
        node_indices = []
        
        for mtxp_bone in mtxp_skeleton.data.bones:
            bone_matrix = mtxp_bone.matrix_local.transposed().inverted()
            node_index = node_bone_index[mtxp_bone.name]
            
            bone_matrices.append( bone_matrix )
            
            node_indices.append( node_index )
            
            
        mtxp_object = BMLMtxpSection()
        
        mtxp_object.node_index_list_offset, mtxp_object.matrices_offset = (mtxp_rewrite_data[0][2], mtxp_rewrite_data[0][3])
        
        mtxp_object.bone_count, mtxp_object.matrices_floats, mtxp_object.node_indices = (len(mtxp_skeleton.data.bones), bone_matrices, node_indices)
        
        mtxp_object.Write(out, mtxp_rewrite_data[0][0], mtxp_rewrite_data[0][1])
        
        ###################################################################
        out.seek(draw_start)
        
        draw_obj = BMLDrawSection()
        
        for i, base_mesh in enumerate(base_meshes):
            mat = base_mesh.data.materials[0]
            
            if mat in mats:
                if base_mesh.name == "unified_mesh":
                    draw_obj.node_index = draw_obj.node_index
                    
                else:
                    draw_obj.node_index = node_bone_index.get(base_mesh.name.split("Shape")[0])
                    
                draw_obj.mesh_index = i
                draw_obj.material_index = mats.index(mat)
                
                draw_obj.Write(out)
                
        ################################################################### 
        out.seek(txtr_start)
        
        txtr_obj = BMLTxtrSection()
        
        mesh_obj = bpy.context.active_object

        for i, tex_file_name in enumerate(mesh_obj.texture_names):
            name = tex_file_name.name
            
            txtr_obj.name = name
            txtr_obj.datasize = txtr_rewrite_data[i][0]
            txtr_obj.pos_name = txtr_rewrite_data[i][1]
            
            txtr_obj.Write(out)
            
        ###################################################################        
        out.seek(pof_start)
        
        out.write("POF0".encode("utf-8"))
        write_uint(out, ENDIANNESS, pof_size)
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        write_uint(out, ENDIANNESS, len(POF) + 1)
        
        for pof in POF:
            write_uint(out, ENDIANNESS, pof)
            
        
        write_alignment(4, out, out.tell())
        
        
        # Sentinel
        out.write(b"\x00" * 10)
        out.write(b"\x04")
        out.write(b"\x00")
        
