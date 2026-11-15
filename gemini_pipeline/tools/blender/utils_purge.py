try:
    import bpy
except ImportError:
    bpy = None

from tools.utils.logger import get_logger

logger = get_logger("BlenderPurge")

def purge_orphan_data_blocks():
    if bpy is None:
        logger.warning("bpy module not available outside Blender environment. Skipping purge.")
        return

    collections = [
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.textures,
        bpy.data.images,
        bpy.data.curves,
        bpy.data.actions,
        bpy.data.cameras,
        bpy.data.lights,
    ]

    removed_count = 0
    changed = True
    while changed:
        changed = False
        for collection in collections:
            for block in list(collection):
                if block.users == 0:
                    collection.remove(block)
                    removed_count += 1
                    changed = True

    try:
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    except Exception as e:
        logger.warning(f"Native orphans_purge warning: {e}")

    logger.info(f"Purged {removed_count} orphan Blender data blocks.")
