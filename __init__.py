bl_info = {
    "name": "Call to Exist Importer and Exporter",
    "author": "haru233",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "File > Import, File > Export, Drag-And-Drop (Import)",
    "description": "Import and Export Tokyo Ghoul:re [Call to Exist] Game Models",
    "category": "Import-Export",
}


import bpy
import bpy.utils.previews as previews
from bpy.types import Operator, FileHandler, PropertyGroup, Menu, Panel, Collection, UIList, OperatorFileListElement
from bpy.props import StringProperty, BoolProperty, CollectionProperty, IntProperty, PointerProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
import os


from .blender_import import *
from .blender_export import *


class ExportCollectionItem(PropertyGroup):
    name: StringProperty()
    export: BoolProperty(name="Export", default=True)


def init_collection_properties():
    bpy.types.Scene.export_collections = CollectionProperty(type=ExportCollectionItem)
    bpy.types.Scene.export_collections_index = IntProperty(default=0)

def populate_collections():
    scene = bpy.context.scene
    scene.export_collections.clear()
    for col in bpy.data.collections:
        item = scene.export_collections.add()
        item.name = col.name
        item.export = True
        



class TextureNameItem(PropertyGroup):
    name: StringProperty(name="Texture Name")

class OBJECT_UL_texture_names(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "name", text="", emboss=True, icon='TEXTURE')
        
class OBJECT_PT_texture_names(bpy.types.Panel):
    bl_label = "Texture Names (CtE)"
    bl_idname = "OBJECT_PT_texture_names"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    def draw(self, context):
        layout = self.layout
        obj = context.object

        if obj is None:
            return

        layout.template_list(
            "OBJECT_UL_texture_names",
            "",
            obj,
            "texture_names",
            obj,
            "texture_names_index",
        )
        
############################################################################
    
class IMPORT_OT_CTE_FileView(Operator, ImportHelper):
    bl_idname = "import_scene.cte"
    bl_label = "Import CTE Model File (_BML)"
    bl_options = {'PRESET', 'UNDO'}
    
    files: CollectionProperty(type=OperatorFileListElement)
    directory: StringProperty(subtype="DIR_PATH")
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        layout.label(text="Import Options")
        layout.prop(scene, "flip_uv_v_axis")
        layout.prop(scene, "reverse_winding_order")
        layout.prop(scene, "import_lods")

    def execute(self, context):
        if self.files:
            for f in self.files:
                full_path = os.path.join(self.directory, f.name)
                BlenderImport(full_path)
                print(f"Imported: {full_path}")

        return {'FINISHED'}


class EXPORT_OT_CTE(Operator, ExportHelper):
    bl_idname = "export_scene.cte"
    bl_label = "Export CTE Model File (_BML)"
    bl_options = {'PRESET'}
    
    filename_ext = ""
    
    filter_glob: StringProperty(default="*", options={'HIDDEN'},)
    
    def invoke(self, context, event):
        populate_collections()  # populate checkbox list
        return super().invoke(context, event)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        layout.label(text="Collections:")
        for item in scene.export_collections:
            
            layout.prop(item, "export", text=item.name)
            
        layout.separator()
        layout.label(text="Export Options")
        layout.prop(scene, "flip_uv_v_avis")
        layout.prop(scene, "reverse_winding_order")
        

    def execute(self, context):
        scene = context.scene
        base_dir = os.path.dirname(self.filepath)
        filename = os.path.basename(self.filepath)

        exported_count = 0
        for item in scene.export_collections:
            if item.export:
                collection = bpy.data.collections.get(item.name)
                collection_file = os.path.join(base_dir, filename)
                
                depsgraph = bpy.context.evaluated_depsgraph_get()
                mesh_objects = [obj.evaluated_get(depsgraph) for obj in collection.objects if obj.type == "MESH"]
                
                # Export each collection to its own file
                BlenderExport(collection, collection_file, mesh_objects)
                exported_count += 1

        self.report({'INFO'}, f"Exported {exported_count} collections")
        return {'FINISHED'}
    

class IMPORT_OT_CTE_DragAndDrop(Operator):
    bl_idname = "import_scene.cte_drag_and_drop"
    bl_label = "Import CTE Model File (_BML)"
    bl_options = {'PRESET', 'UNDO'}

    # Multi-file support
    files: bpy.props.CollectionProperty(type=OperatorFileListElement)
    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        if self.files:
            for f in self.files:
                full_path = os.path.join(self.directory, f.name)
                BlenderImport(full_path)
                print(f"Imported: {full_path}")

        return {'FINISHED'}



class Mesh_FileHandler(FileHandler):
    bl_idname = "MESH_FILEHANDLER"
    bl_label = "Import CTE Model File (_BML)"
    bl_import_operator = "import_scene.te_drag_and_drop"
    bl_file_extensions = ""
    
    @classmethod
    def poll_drop(cls, context):
        return context.area and context.area.type == "VIEW_3D"




def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_CTE_FileView.bl_idname, text="CTE (_BML)")


def menu_func_export(self, context):
    self.layout.operator(EXPORT_OT_CTE.bl_idname, text="CTE (_BML)")





classes = (
    IMPORT_OT_CTE_FileView,
    EXPORT_OT_CTE,
    IMPORT_OT_CTE_DragAndDrop,
    Mesh_FileHandler,
    
    TextureNameItem,
    OBJECT_UL_texture_names,
    OBJECT_PT_texture_names
    
    

    
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
   
    bpy.types.Scene.flip_uv_v_axis = bpy.props.BoolProperty(
        name="Flip UV V-Axis",
        default=False
    )
    
    bpy.types.Scene.reverse_winding_order = bpy.props.BoolProperty(
        name="Reverse Triangle Winding Order",
        default=False
    )
    
    bpy.types.Scene.import_lods = bpy.props.BoolProperty(
        name="Import LODs for Each Mesh",
        default=False
    )

    bpy.types.Object.texture_names = bpy.props.CollectionProperty(
        type=TextureNameItem
    )

    bpy.types.Object.texture_names_index = bpy.props.IntProperty()



def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    
    if hasattr(bpy.types.Scene, "flip_uv_v_axis"):
        del bpy.types.Scene.flip_uv_v_axis
        
    if hasattr(bpy.types.Scene, "reverse_winding_order"):
        del bpy.types.Scene.reverse_winding_order
        
    if hasattr(bpy.types.Scene, "import_lods"):
        del bpy.types.Scene.import_lods
        
    if hasattr(bpy.types.Object, "texture_names"):
        del bpy.types.Object.texture_names
        
    if hasattr(bpy.types.Object, "texture_names_index"):
        del bpy.types.Object.texture_names_index
        
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
