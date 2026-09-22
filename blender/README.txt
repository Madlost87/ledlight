Save the working Blender file here as:

anamorphic_lamp.blend

Project scripts derive ANAMORPHIC_LAMP as the parent directory of this
blender folder via bpy.data.filepath. If the .blend has not been saved,
the scripts stop with a clear error instead of using computer-specific
absolute paths.
