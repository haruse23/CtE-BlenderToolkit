from .helpers import *
import os

from io import BytesIO
from pathlib import Path

ENDIANNESS = "<"

class BMLSection:
    def __init__(self):
        self.name = ""
        self.size = 0
        self.unk = b""
        self.alignment_num = 0
        
        self.section_data_offset = 0
        
        self.section_data = b""
        
        
    def ReadBMLSection(self, f):
        self.name = f.read(4).decode("ascii")
        
        self.size = read_uint(f, ENDIANNESS)
        
        self.unk = f.read(2) # 00 00
        self.alignment_num = read_ushort(f, ENDIANNESS)
        
        self.section_data_offset = f.tell()
        
        self.section_data = f.read(self.size)
        
        align(self.alignment_num, f, f.tell()) # 4-byte alignment
        
        
        
    def WriteBMLSection(self, out):
        out.write(self.name.encode("utf-8"))
        write_uint(out, ENDIANNESS, self.size)
        out.write(b"\x00" * 2)
        
        write_ushort(out, ENDIANNESS, 4) # Use 4-byte alignment always
        
        
        
    
    
    
        
class BMLMtxpSection:
    def Read(self, bytesio_cursor, f):
        self.node_index_list_offset = read_uint64(bytesio_cursor, ENDIANNESS)
        self.matrices_offset = read_uint64(bytesio_cursor, ENDIANNESS) # Inverse bind pose
        bytesio_cursor.seek(2, 1)
        self.bone_count = int.from_bytes(bytesio_cursor.read(6), byteorder='little')
        
        
        f.seek(self.matrices_offset)
        
        self.matrices_floats = []
        for i in range(self.bone_count):
            values = struct.unpack("<16f", f.read(64))
            
            self.matrices_floats.append(values)
            
        
        
        f.seek(self.node_index_list_offset)
        
        self.node_indices = []
        for i in range(self.bone_count):
            node_index = read_uint(f, ENDIANNESS)
            
            self.node_indices.append(node_index)
            
            
            
        
    
    
    
    def Write(self, out, datasize1, datasize2):
        out.write("MTXP".encode("utf-8"))
        write_uint(out, ENDIANNESS, 24) # 0x18
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        self.pos1 = out.tell()
        write_uint64(out, ENDIANNESS, self.node_index_list_offset)
        
        self.pos2 = out.tell()
        write_uint64(out, ENDIANNESS, self.matrices_offset)
        
        out.write(b"\x00" * 2)
        write_uint(out, ENDIANNESS, self.bone_count)
        write_alignment(4, out, out.tell())
        
        # DATA, Matrices
        
        
        out.write("DATA".encode("utf-8"))
        write_uint(out, ENDIANNESS, datasize1)  # Size
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        self.pos01 = out.tell()
        for matrix in self.matrices_floats:
            out.write(struct.pack("<16f", *(v for row in matrix for v in row)))
            
        self.pos1end = out.tell()
        
        write_alignment(4, out, out.tell())
            
        
        
        # DATA, Node Indices
        
        
        out.write("DATA".encode("utf-8"))
        write_uint(out, ENDIANNESS, datasize2)  # Size
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        self.pos02 = out.tell()
        for node_index in self.node_indices:
            write_uint(out, ENDIANNESS, node_index)
            
        self.pos2end = out.tell()
        
        write_alignment(4, out, out.tell())
        
        



class BMLMeshSection:
    def __init__(self):
        self.MeshNameOffset = 0
        self.MeshVertexBufferOffset = 0
        
        self.MeshIndexBufferOffset = 0
        self.MeshIndexBufferInfoOffset = 0
        
        self.unk_0 = 0
        
        self.MeshLOD1Offset = 0
        self.MeshLOD2Offset = 0
        self.MeshLOD3Offset = 0
        self.MeshLOD4Offset = 0
        
        self.unk_1 = 0
        self.value = 0
        
        self.IndexCount = 0
        self.VertexCount = 0
        
        self.IndexSize = 0
        self.VertexStride = 0
        
        
        
        
    def ReadBMLMeshSection(self, f):
        self.MeshNameOffset = read_uint64(f, ENDIANNESS)
        self.MeshVertexBufferOffset = read_uint64(f, ENDIANNESS)
        
        self.MeshIndexBufferOffset = read_uint64(f, ENDIANNESS)
        self.MeshIndexBufferInfoOffset = read_uint64(f, ENDIANNESS)
        
        self.unk_0 = read_uint64(f, ENDIANNESS)
        
        self.MeshLOD1Offset = read_uint64(f, ENDIANNESS)
        self.MeshLOD2Offset = read_uint64(f, ENDIANNESS)
        self.MeshLOD3Offset = read_uint64(f, ENDIANNESS)
        self.MeshLOD4Offset = read_uint64(f, ENDIANNESS)
        
        self.unk_1 = read_uint(f, ENDIANNESS)
        self.value = read_uint(f, ENDIANNESS)
        
        
        self.IndexCount = read_uint(f, ENDIANNESS)
        self.VertexCount = read_uint(f, ENDIANNESS)
        
        self.IndexSize = read_ushort(f, ENDIANNESS)
        self.VertexStride = read_ushort(f, ENDIANNESS)
        
        
        
    def Write(self, out, blend_weights, mesh_name, lod_count):
        if not "LOD" in mesh_name:
            out.write("MESH".encode("utf-8"))
            
        else:
            out.write("LODM".encode("utf-8"))
            
        write_uint(out, ENDIANNESS, 104) # 0x68
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        self.pos1 = out.tell()
        write_uint64(out, ENDIANNESS, self.MeshNameOffset)
        
        self.pos2 = out.tell()
        write_uint64(out, ENDIANNESS, self.MeshVertexBufferOffset)
        
        self.pos3 = out.tell()
        write_uint64(out, ENDIANNESS, self.MeshIndexBufferOffset)
        
        self.pos4 = out.tell()
        write_uint64(out, ENDIANNESS, self.MeshIndexBufferInfoOffset)
        
        write_uint64(out, ENDIANNESS, 0) # unk_0
        
        
        self.pos5 = out.tell()
        write_uint64(out, ENDIANNESS, self.MeshLOD1Offset)
        
        self.pos6 = out.tell()
        write_uint64(out, ENDIANNESS, self.MeshLOD2Offset)
        
        self.pos7 = out.tell()
        write_uint64(out, ENDIANNESS, self.MeshLOD3Offset)
        
        self.pos8 = out.tell()
        write_uint64(out, ENDIANNESS, self.MeshLOD4Offset)
        
        
        write_uint(out, ENDIANNESS, 0x40490429) # unk_1
        write_uint(out, ENDIANNESS, 0) # value
        
        write_uint(out, ENDIANNESS, self.IndexCount)
        write_uint(out, ENDIANNESS, self.VertexCount)
        
        write_ushort(out, ENDIANNESS, self.IndexSize)
        write_ushort(out, ENDIANNESS, self.VertexStride)
        
        # max bone influences per vertex for this mesh (1-4)
        max_infl = max((sum(1 for w in vw[:4] if w > 1e-6) for vw in blend_weights), default=1)
        max_infl = max(1, min(4, max_infl))

        out.write(bytes([1, max_infl, 1, 1, 0, 1, lod_count, 0, 0, 0, 0, 0]))
        
        write_alignment(4, out, out.tell())
        
        
        
        
        
        
        
        
        
class Vertex:
    def __init__(self):
    
        self.Vertices = []
        
    def ReadVertices(self, f, vertex_count, vertex_stride, value):
        for i in range(0, vertex_count * vertex_stride, vertex_stride):
            # positions
            
            px = read_float(f, ENDIANNESS)
            py = read_float(f, ENDIANNESS)
            pz = read_float(f, ENDIANNESS)
            
            positions = [px, py, pz]
            
            # blendweights
            
            bw1 = read_float(f, ENDIANNESS)
            bw2 = read_float(f, ENDIANNESS)
            bw3 = read_float(f, ENDIANNESS)
            bw4 = read_float(f, ENDIANNESS)
            
            blendweights = [bw1, bw2, bw3, bw4]
            
            # blendindices
            
            bi1 = read_uint8(f, ENDIANNESS)
            bi2 = read_uint8(f, ENDIANNESS)
            bi3 = read_uint8(f, ENDIANNESS)
            bi4 = read_uint8(f, ENDIANNESS)
            
            blendindices = [bi1, bi2, bi3, bi4]
            
            
            # blendweights and blendindices usage_index 1
            
            bw1_1 = read_float(f, ENDIANNESS)
            bw2_1 = read_float(f, ENDIANNESS)
            bw3_1 = read_float(f, ENDIANNESS)
            bw4_1 = read_float(f, ENDIANNESS)
            
            blendweights_1 = [bw1_1, bw2_1, bw3_1, bw4_1]
            
            bi1_1 = read_uint8(f, ENDIANNESS)
            bi2_1 = read_uint8(f, ENDIANNESS)
            bi3_1 = read_uint8(f, ENDIANNESS)
            bi4_1 = read_uint8(f, ENDIANNESS)
            
            blendindices_1 = [bi1_1, bi2_1, bi3_1, bi4_1]
            
            # normals
            
            nx = read_halffloat(f, ENDIANNESS)
            ny = read_halffloat(f, ENDIANNESS)
            nz = read_halffloat(f, ENDIANNESS)
            nw = read_halffloat(f, ENDIANNESS)
            
            normals = [nx, ny, nz, nw]
            
            # colors, R8G8B8A8_UNORM
            
            c1 = read_uint8(f, ENDIANNESS) / 255.0
            c2 = read_uint8(f, ENDIANNESS) / 255.0
            c3 = read_uint8(f, ENDIANNESS) / 255.0
            c4 = read_uint8(f, ENDIANNESS) / 255.0
            
            colors = [c1, c2, c3, c4]
            
            if value:
                f.seek(value, 1)
            
            # texcoords
            
            t1 = read_halffloat(f, ENDIANNESS)
            t2 = read_halffloat(f, ENDIANNESS)
            
            texcoords = [t1, t2]
            
            # tangents
            
            tx = read_halffloat(f, ENDIANNESS)
            ty = read_halffloat(f, ENDIANNESS)
            tz = read_halffloat(f, ENDIANNESS)
            tw = read_halffloat(f, ENDIANNESS)
            
            tangents = [tx, ty, tz, tw]
            
            
            # binormals
            
            bx = read_halffloat(f, ENDIANNESS)
            by = read_halffloat(f, ENDIANNESS)
            bz = read_halffloat(f, ENDIANNESS)
            bw = read_halffloat(f, ENDIANNESS)
            
            binormals = [bx, by, bz, bw]
            
            Vertex = {"positions": positions, "blendweights": blendweights, "blendindices": blendindices, "blendweights_1": blendweights_1, "blendindices_1": blendindices_1, "normals": normals, "colors": colors, "texcoords": texcoords, "binormals": binormals, "tangents": tangents}
            
            
            self.Vertices.append(Vertex)
            
        
    
    def Write(self, out):
        out.write("DATA".encode("utf-8"))
        write_uint(out, ENDIANNESS, self.size)  # Size
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        self.pos0 = out.tell()
        for i in range(self.vertex_count):
            # positions
            
            write_float(out, ENDIANNESS, self.vertices["positions"][i][0])
            write_float(out, ENDIANNESS, self.vertices["positions"][i][1])
            write_float(out, ENDIANNESS, self.vertices["positions"][i][2])
            
            # blendweights
            
            write_float(out, ENDIANNESS, self.vertices["blendweights"][i][0])
            write_float(out, ENDIANNESS, self.vertices["blendweights"][i][1])
            write_float(out, ENDIANNESS, self.vertices["blendweights"][i][2])
            write_float(out, ENDIANNESS, self.vertices["blendweights"][i][3])
            
            # blendindices
            
            write_uint8(out, ENDIANNESS, self.vertices["blendindices"][i][0])
            write_uint8(out, ENDIANNESS, self.vertices["blendindices"][i][1])
            write_uint8(out, ENDIANNESS, self.vertices["blendindices"][i][2])
            write_uint8(out, ENDIANNESS, self.vertices["blendindices"][i][3])

            # blendweights and blendindices usage_index 1
            
            write_float(out, ENDIANNESS, self.vertices["blendweights_1"][i][0])
            write_float(out, ENDIANNESS, self.vertices["blendweights_1"][i][1])
            write_float(out, ENDIANNESS, self.vertices["blendweights_1"][i][2])
            write_float(out, ENDIANNESS, self.vertices["blendweights_1"][i][3])
            
            write_uint8(out, ENDIANNESS, self.vertices["blendindices_1"][i][0])
            write_uint8(out, ENDIANNESS, self.vertices["blendindices_1"][i][1])
            write_uint8(out, ENDIANNESS, self.vertices["blendindices_1"][i][2])
            write_uint8(out, ENDIANNESS, self.vertices["blendindices_1"][i][3])

            # normals
            
            write_halffloat(out, ENDIANNESS, self.vertices["normals"][i][0])
            write_halffloat(out, ENDIANNESS, self.vertices["normals"][i][1])
            write_halffloat(out, ENDIANNESS, self.vertices["normals"][i][2])
            write_halffloat(out, ENDIANNESS, 0)

            # colors, R8G8B8A8_UNORM, first color attribute
            
            write_uint8(out, ENDIANNESS, int(round(self.vertices["colors"][i][0][0] * 255.0)) )
            write_uint8(out, ENDIANNESS, int(round(self.vertices["colors"][i][0][1] * 255.0)) )
            write_uint8(out, ENDIANNESS, int(round(self.vertices["colors"][i][0][2]* 255.0)) )
            write_uint8(out, ENDIANNESS, int(round(self.vertices["colors"][i][0][3] * 255.0)) )
 
            # texcoords, first UV channel
            write_halffloat(out, ENDIANNESS, self.vertices["texcoords"][i][0][0])
            write_halffloat(out, ENDIANNESS, self.vertices["texcoords"][i][0][1])
 
            # tangents
            
            write_halffloat(out, ENDIANNESS, self.vertices["tangents"][i][0])
            write_halffloat(out, ENDIANNESS, self.vertices["tangents"][i][1])
            write_halffloat(out, ENDIANNESS, self.vertices["tangents"][i][2])
            write_halffloat(out, ENDIANNESS, 0)
            
            # binormals
            
            write_halffloat(out, ENDIANNESS, self.vertices["binormals"][i][0])
            write_halffloat(out, ENDIANNESS, self.vertices["binormals"][i][1])
            write_halffloat(out, ENDIANNESS, self.vertices["binormals"][i][2])
            write_halffloat(out, ENDIANNESS, 0)
        
        self.pos_end = out.tell()
        write_alignment(4, out, out.tell())
            
            
        
        
class Index:
    def __init__(self):
        
        self.Indices = []
        
        
    def ReadIndices(self, f, index_count, index_size):
        for i in range(0, index_count * index_size, index_size):
            if index_size == 2:
                index = read_ushort(f, ENDIANNESS)
                
            else:
                index = read_uint(f, ENDIANNESS)
                
            self.Indices.append(index)
            
            
    def Write(self, out, VertexCount):
        
        if VertexCount > 65535:
            out.write("DATA".encode("utf-8"))
            write_uint(out, ENDIANNESS, self.size)  # Size
            out.write(b"\x00" * 2)
            write_ushort(out, ENDIANNESS, 4) # Alignment_num
            
            self.index_write_start = out.tell()
            for index in self.Indices:
                    write_uint(out, ENDIANNESS, index)
                
        else:
            out.write("DATA".encode("utf-8"))
            write_uint(out, ENDIANNESS, self.size)  # Size
            out.write(b"\x00" * 2)
            write_ushort(out, ENDIANNESS, 4) # Alignment_num
            
            self.index_write_start = out.tell()
            for index in self.Indices:   
                write_ushort(out, ENDIANNESS, index)
        
        self.index_write_end = out.tell()
        write_alignment(4, out, out.tell())
        
        
            

class Mesh:
    def __init__(self, vertices, indices, name):
        self.Vertices = vertices
        self.Indices = indices
        self.Name = name
        
        


class BMLMaterialSection:
    def __init__(self):
        self.MaterialNameOffset = 0
        self.TextureNameOffset = 0
        
        
    def ReadBMLMaterialSection(self, f):
        self.MaterialNameOffset = read_uint64(f, ENDIANNESS)
        self.TextureNameOffset = read_uint64(f, ENDIANNESS)
        
        
    def Write(self, out):
        out.write("MATE".encode("utf-8"))
        write_uint(out, ENDIANNESS, self.size)
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        self.pos_mat_start = out.tell()
        
        self.pos1 = out.tell()
        write_uint64(out, ENDIANNESS, self.MaterialNameOffset)
        
        self.pos2 = out.tell()
        write_uint64(out, ENDIANNESS, self.TextureNameOffset)
        
        out.write(b"\x00\x00\x00\xFF" * 2)  # unknown, preserve
        out.write(b"\xFF\xFF\xFF\xFF")  # unknown, preserve
        out.write(b"\x00\x00\x00\x00")  # unknown, preserve
        
        write_uint(out, ENDIANNESS, calculate_hash(self.MaterialName))
        
        out.write(struct.pack("<9f", 0, -0, 0, 1, 1, 0, 0, 0, 0)) # unknown, preserve
        
        self.pos0 = out.tell()
        
        write_alignment(4, out, out.tell())
        
        
        
        out.write("DATA".encode("utf-8"))
        write_uint(out, ENDIANNESS, self.size_matname_data)
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
                
        self.pos_name1 = out.tell()
        out.write(self.MaterialName.encode("ascii") + b"\x00")
        self.pos_name2 = out.tell()
        
        write_alignment(4, out, out.tell())
        
        
        out.write("DATA".encode("utf-8"))
        write_uint(out, ENDIANNESS, self.size_texturename_data)
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        self.pos_name3 = out.tell()
        
        if self.TextureName == "\x00":
            out.write(self.TextureName.encode("ascii"))
            
        else:
            out.write(self.TextureName.encode("ascii") + ".png".encode("ascii") + b"\x00")
            
        self.pos_name4 = out.tell()
        
        write_alignment(4, out, out.tell())
        
        
        
        
        
        
    
        
        
class BMLDrawSection:
    def Read(self, f):
        self.node_index = read_uint(f, ENDIANNESS)
        self.mesh_index = read_uint(f, ENDIANNESS)
        self.material_index = read_uint(f, ENDIANNESS)
        self.unk = read_uint(f, ENDIANNESS)
    
    
    def Write(self, out):
        out.write("DRAW".encode("utf-8"))
        write_uint(out, ENDIANNESS, 16) # 0x10
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        write_uint(out, ENDIANNESS, self.node_index)
        write_uint(out, ENDIANNESS, self.mesh_index)
        write_uint(out, ENDIANNESS, self.material_index)
        write_uint(out, ENDIANNESS, 0)
        
        write_alignment(4, out, out.tell())
        
        
        
class BMLBoneNodeSection:
    def __init__(self):
        self.BoneNameOffset = 0
        self.ParentNameOffset = 0
        
        self.BonePositions = [0] * 3
        self.BoneScale = [0] * 3
        self.BoneRotation = [0] * 3
        
        self.BoneHash = 0
        self.ParentIndex = 0
        
    def ReadBMLBoneNodeSection(self, f):
        self.BoneNameOffset = read_uint64(f, ENDIANNESS)
        self.ParentNameOffset = read_uint64(f, ENDIANNESS)
        
        # Bone Positions
        px = read_float(f, ENDIANNESS)
        py = read_float(f, ENDIANNESS)
        pz = read_float(f, ENDIANNESS)
        
        self.BonePositions = [px, py, pz]
        
        # Bone Scale
        sx = read_float(f, ENDIANNESS)
        sy = read_float(f, ENDIANNESS)
        sz = read_float(f, ENDIANNESS)
        
        self.BoneScale = [sx, sy, sz]
        
        # Bone Rotation
        rx = read_float(f, ENDIANNESS)
        ry = read_float(f, ENDIANNESS)
        rz = read_float(f, ENDIANNESS)
        
        self.BoneRotation = [rx, ry, rz]
        
        f.seek(40, 1) # Unknown bytes
        
        self.BoneHash = read_uint(f, ENDIANNESS)
        
        self.ParentIndex = read_uint(f, ENDIANNESS)
        
        f.seek(4, 1) # Unknown bytes
        
        
        
        
    def Write(self, out, base_meshes, mesh_bounds):
        out.write("NODE".encode("utf-8"))
        write_uint(out, ENDIANNESS, 104) # 0x68
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        self.pos1 = out.tell()
        write_uint64(out, ENDIANNESS, self.BoneNameOffset)
        
        self.pos2 = out.tell()
        write_uint64(out, ENDIANNESS, self.ParentNameOffset)
        
        for position in self.BonePosition:
            write_float(out, ENDIANNESS, position)
            
        for scale in self.BoneScale:
            write_float(out, ENDIANNESS, scale)
            
        for i, rotation in enumerate(self.BoneRotation):
            write_float(out, ENDIANNESS, rotation)
            
        for base_mesh in base_meshes:
            if self.bone_name in base_mesh.name:
                min_pos = mesh_bounds.get(base_mesh.name)[0] if mesh_bounds else (0, 0, 0)
                max_pos = mesh_bounds.get(base_mesh.name)[1] if mesh_bounds else (0, 0, 0)
                sphere_center = mesh_bounds.get(base_mesh.name)[2] if mesh_bounds else (0, 0, 0)
                radius = mesh_bounds.get(base_mesh.name)[3] if mesh_bounds else 0
                
                for pos in min_pos:
                    write_float(out, ENDIANNESS, pos)
                
                for pos in max_pos:
                    write_float(out, ENDIANNESS, pos)
                    
                for pos in sphere_center:
                    write_float(out, ENDIANNESS, pos)
                    
                write_float(out, ENDIANNESS, radius)
                    
                
                write_uint(out, ENDIANNESS, calculate_hash(self.bone_name))
                
                write_int(out, ENDIANNESS, self.parent_index)
        
        
                out.write(b"\x04")  # preserve, mesh appears
                out.write(b"\x01")  # preserve, mesh appears
                out.write(b"\x00" * 2)
                
                break
        else:
            out.write(b"\xFF\xFF\x7F\x7F" * 3)
            out.write(b"\xFF\xFF\x7F\xFF" * 3)
            out.write(b"\x00\x00\x00\x00" * 4)
                
            
            write_uint(out, ENDIANNESS, calculate_hash(self.bone_name))
            
            write_int(out, ENDIANNESS, self.parent_index)
                
        
            out.write(b"\x01")  # preserve, mesh appears
            out.write(b"\x01")  # preserve, mesh appears
            out.write(b"\x00" * 2)
                
                
                
        
        write_alignment(4, out, out.tell())
            
            
            
    
        
class BMLTxtrSection():
    def Read(self, f):
        magicDATA = read_uint(f, ENDIANNESS)
        sizeDATA = read_uint(f, ENDIANNESS)
        unk0DATA = read_ushort(f, ENDIANNESS)
        alignment_numDATA = read_ushort(f, ENDIANNESS)
        
        self.tex_name = f.read(sizeDATA).decode("ascii")
        
        align(alignment_numDATA, f, f.tell())
        
   
    def Write(self, out):
        out.write("TXTR".encode("utf-8"))
        write_uint(out, ENDIANNESS, 8) # 0x68
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        self.posname_pos = out.tell()
        write_uint(out, ENDIANNESS, self.pos_name)
        write_uint(out, ENDIANNESS, 0)
        
        write_alignment(4, out, out.tell())
        
        
        out.write("DATA".encode("utf-8"))
        write_uint(out, ENDIANNESS, self.datasize) # 0x68
        out.write(b"\x00" * 2)
        write_ushort(out, ENDIANNESS, 4) # Alignment_num
        
        self.pos0 = out.tell()
        out.write(self.name.encode("ascii") + b"\x00")
        self.pos1 = out.tell()
        
        
        write_alignment(4, out, out.tell())
        
        



def ProcessMesh(bytesio_instance, f):
    mesh = BMLMeshSection()

    mesh.ReadBMLMeshSection(bytesio_instance)

    mesh_name = ""

    if mesh.MeshNameOffset != 0:
        f.seek(mesh.MeshNameOffset)

        mesh_name = read_cstring(f)

    f.seek(mesh.MeshVertexBufferOffset)

    mesh_vertex_buffer = f.read(
        mesh.VertexCount * mesh.VertexStride
    )

    f.seek(mesh.MeshIndexBufferOffset)

    mesh_index_buffer = f.read(
        mesh.IndexCount * mesh.IndexSize
    )

    vertex = Vertex()

    vertex.ReadVertices(BytesIO(mesh_vertex_buffer), mesh.VertexCount, mesh.VertexStride, mesh.value)

    index = Index()

    index.ReadIndices(BytesIO(mesh_index_buffer), mesh.IndexCount, mesh.IndexSize)

    mesh_instance = Mesh(
        vertex.Vertices,
        index.Indices,
        mesh_name
    )

    return (mesh, mesh_instance)
    

def ParseMeshes(filepath):
    with open(filepath, "rb") as f:
        bml_section = BMLSection()
        
        bml_section.ReadBMLSection(f)
        
        MeshSections = []
        LodSections = []
        
        MaterialSections = []
        
        BoneNodeSections = []
        
        MTXP_Section = None
        
        DrawSections = []
        
        TxtrSections = []
        
        while f.tell() < os.path.getsize(filepath):
            section = BMLSection()
            
            section.ReadBMLSection(f)
            
            if section.name == "MESH":
                MeshSections.append(section)
                
            elif section.name == "LODM":
                LodSections.append( {"offset": section.section_data_offset, "section": section} )
                
            elif section.name == "MATE":
                MaterialSections.append(section)
            
            elif section.name == "NODE":
                BoneNodeSections.append(section)
                
            elif section.name == "MTXP":
                MTXP_Section = section
        
            elif section.name == "DRAW":
                DrawSections.append(section)
                
            elif section.name == "TXTR":
                txtr_section_obj = BMLTxtrSection()
                
                txtr_section_obj.Read(f)
                
                TxtrSections.append(txtr_section_obj)
        
        
        
        
        Meshes = []
        
        
        for mesh_section in MeshSections:
            LODs = [] # Each Mesh's LODs (including LOD0)
            
            mesh_section_bytesio = BytesIO(mesh_section.section_data)
            
            mesh, mesh_instance = ProcessMesh(mesh_section_bytesio, f) # LOD0
            
            LODs.append(mesh_instance)
            
            for lod_dict in LodSections:
                offset = lod_dict["offset"]
                lod_section = lod_dict["section"]
                
                if offset == mesh.MeshLOD1Offset or offset == mesh.MeshLOD2Offset or offset == mesh.MeshLOD3Offset or offset == mesh.MeshLOD4Offset:
                    lod_section_bytesio = BytesIO(lod_section.section_data)
                    
                    lod, lod_instance = ProcessMesh(lod_section_bytesio, f)
                    
                    LODs.append(lod_instance)
                    
                    
            Meshes.append(LODs)
            
        
        Materials = []
        for material_section in MaterialSections:
            material_section_bytesio = BytesIO(material_section.section_data)
                        
            section = BMLMaterialSection()
            
            section.ReadBMLMaterialSection(material_section_bytesio)
            
            if section.MaterialNameOffset != 0 and section.TextureNameOffset != 0:
                f.seek(section.MaterialNameOffset)
                
                material_name = read_cstring(f)
                
                f.seek(section.TextureNameOffset)
                
                texture_name = read_cstring(f)
                
            
            Materials.append( {"MaterialName": material_name, "TextureName": texture_name} )
        
        
        
        
        BoneNodes = []
        for bone_node_section in BoneNodeSections:
            node_section_bytesio = BytesIO(bone_node_section.section_data)
            
            section = BMLBoneNodeSection()
            
            section.ReadBMLBoneNodeSection(node_section_bytesio)
            
            if section.BoneNameOffset != 0 and section.ParentNameOffset != 0:
                f.seek(section.BoneNameOffset)
                
                bone_name = read_cstring(f)
                
                f.seek(section.ParentNameOffset)
                
                parent_name = read_cstring(f)
                
            
            BoneNodes.append( {"BoneName": bone_name, "BoneHash": section.BoneHash, "ParentIndex": section.ParentIndex, "ParentName": parent_name, "BonePositions": section.BonePositions, "BoneScale": section.BoneScale, "BoneRotation": section.BoneRotation} )
        
        
        
        
        # MTXP
        mtxp_section_bytesio = BytesIO(MTXP_Section.section_data)
        
        mtxp_section = BMLMtxpSection()
        
        mtxp_section.Read(mtxp_section_bytesio, f)
        
        
        # DRAW
        draws = []
        for draw_section in DrawSections:
            draw_section_bytesio = BytesIO(draw_section.section_data)
            
            draw_section = BMLDrawSection()
            
            draw_section.Read(draw_section_bytesio)
            
            draws.append( {"MeshIndex": draw_section.mesh_index, "MaterialIndex": draw_section.material_index} )
        
        
        tex_names = []
        for txtr_section_obj in TxtrSections:
            tex_names.append(txtr_section_obj.tex_name)
        
        
        
    """
    filePath = Path(filepath)
    bmaPath = filePath.with_name(filePath.name.replace("_BML", "_BMA"))
    with open(bmaPath, "rb") as f:
        anhd_section = BMLSection()
        
        anhd_section.ReadBMLSection(f)
        
        
        ansk_section = BMLSection()
        
        ansk_section.ReadBMLSection(f)
        
        ansk_data_offset = struct.unpack_from("<Q", ansk_section.section_data, 0)[0]
        ansk_bone_count = struct.unpack_from("<H", ansk_section.section_data, 8)[0]
        
        f.seek(ansk_data_offset)
        
        ansk_bones = []
        for i in range(ansk_bone_count):
            bone_name_offset = read_uint64(f, ENDIANNESS)
            bone_data_offset = read_uint64(f, ENDIANNESS)
            bone_name_hash = read_uint(f, ENDIANNESS)
            bone_unk = read_uint(f, ENDIANNESS)
            
            ansk_bones.append( {"BoneNameOffset": bone_name_offset, "BoneDataOffset": bone_data_offset, "BoneHash": bone_name_hash} )
            
            
        ansk_bones_data = []
        for ansk_bone in ansk_bones:
            name_offset = ansk_bone["BoneNameOffset"]
            data_offset = ansk_bone["BoneDataOffset"]
            
            
            f.seek(name_offset)
            
            name = read_cstring(f)
            
            f.seek(data_offset)
            
            # Read bone metadata
            f.seek(8, 1) # Skip unknown offset
            
            bone_positions_offset = read_uint64(f, ENDIANNESS)
            
            f.seek(16, 1) # Skip unknown offsets
            
            bone_rotation_offset = read_uint64(f, ENDIANNESS)
            
            f.seek(16, 1) # Skip unknown data
            
            bone_scale_offset = read_uint64(f, ENDIANNESS)
            
            
            # Read bone data
            
            # Positions, vector of 3 floats
            f.seek(bone_positions_offset)
            
            px = read_float(f, ENDIANNESS)
            py = read_float(f, ENDIANNESS)
            pz = read_float(f, ENDIANNESS)
            
            positions = [px, py, pz]
            
            # Rotation, quaternion
            f.seek(bone_rotation_offset)
            
            rx = read_float(f, ENDIANNESS)
            ry = read_float(f, ENDIANNESS)
            rz = read_float(f, ENDIANNESS)
            rw = read_float(f, ENDIANNESS)
            
            rotation = [rx, ry, rz, rw]
            
            
            # Scale, 3 floats = 1
            f.seek(bone_scale_offset)
            
            sx = read_float(f, ENDIANNESS)
            sy = read_float(f, ENDIANNESS)
            sz = read_float(f, ENDIANNESS)
            
            scale = [sx, sy, sz]
            
            
            ansk_bones_data.append( {"BoneName": name, "Positions": positions, "Rotation": rotation, "Scale": scale} )"""
            
            
            
            
            
            
            
            
            
        
        
        
        
    
    
    
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
            
            
    return Meshes, Materials, BoneNodes, mtxp_section, draws, tex_names
                
                
            
            