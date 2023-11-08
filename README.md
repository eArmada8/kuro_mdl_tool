# Kuro MDL mesh export and import
A pair of scripts to get the mesh data out of MDL files and back into MDL files.  The output is in .fmt/.vb/.ib files that are compatible with DarkStarSword Blender import plugin for 3DMigoto, and metadata is in JSON format.

## Tutorials:

Please see the [wiki](https://github.com/eArmada8/kuro_mdl_tool/wiki), and the detailed documentation below.

## Credits:
99.9% of my understanding of the MDL format comes from the reverse engineering work of Julian Uy (github.com/uyjulian), and specifically his MDL to GLTF convertor: https://gist.github.com/uyjulian/9a9d6395682dac55d113b503b1172009

The code to decrypt and decompress CLE assets comes from KuroTools (https://github.com/nnguyen259/KuroTools), and I also looked through MDL convertor in KuroTools by TwnKey (github.com/TwnKey) to understand the MDL format.

None of this would be possible without the work of DarkStarSword and his amazing 3DMigoto-Blender plugin, of course.

I am very thankful for uyjulian, TwnKey, DarkStarSword, the KuroTools team and the Kiseki modding discord for their brilliant work and for sharing that work so freely.

## Requirements:
1. Python 3.10 and newer is required for use of these scripts.  It is free from the Microsoft Store, for Windows users.  For Linux users, please consult your distro.
2. The blowfish, zstandard, numpy and pyquaternion modules for python are needed.  Install by typing "python3 -m pip install blowfish zstandard numpy pyquaternion" in the command line / shell.  (The io, re, struct, sys, os, shutil, glob, base64, json, operator, argparse and itertools modules are also required, but these are all already included in most basic python installations.)
3. The output can be imported into Blender using DarkStarSword's amazing plugin: https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py (tested on commit [c6daca9](https://raw.githubusercontent.com/DarkStarSword/3d-fixes/c6daca90d64b0fb53f2ebf70806e539b8007d328/blender_3dmigoto.py))
4. kuro_mdl_export_meshes.py is dependent on lib_fmtibvb.py, which must be in the same folder.  
kuro_mdl_import_meshes.py is dependent on both kuro_mdl_export_meshes.py and lib_fmtibvb.py.

## Usage:
### kuro_mdl_export_meshes.py
Double click the python script and it will search the current folder for all .mdl files and export the meshes into a folder with the same name as the mdl file.  Additionally, it will output 5 JSON files, one with metadata from the mesh section, another with the data from the materials section, another with the skeleton, and fourth with the MDL version, and (for convenience) a list of textures used by the MDL.

**Command line arguments:**
`kuro_mdl_export_meshes.py [-h] [-c] [-t] [-o] mdl_filename`

`-h, --help`
Shows help message.

`-c, --completemaps`
.vgmap files will have the entire skeleton, with every bone available to the mesh, included with each mesh.  This will result in many empty vertex groups upon import into Blender.  The default behavior is to only include vertex groups that contain at least one vertex.  Complete maps are primarily useful when merging one mesh into another.

`-t, --trim_for_gpu`
Trim vertex buffer for GPU injection (3DMigoto).  Meshes in the MDL contain have 15 vertex buffers (position, normal, tangent, 8x texcoord, 2x color, blendweights and blendindices).  Only 8 of these are actually loaded into GPU memory for most characters (only the first 3 texcoords are loaded, and the 2x color are not loaded).  This option produces smaller .vb files (with matching .fmt files) with the extraneous buffers discarded, so that upon splitting, the buffers can be used for injection with 3DMigoto.  (See here for my vertex buffer splitting tool: https://github.com/eArmada8/vbuffer_merge_split/blob/main/kuro/kuro_vb_split.py)

`-o, --overwrite`
Overwrite existing files without prompting.

**Complete VGMap Setting:**

Many modders prefer that complete VGmaps is the default, rather than a command line option.  You can (permanently) change the default behavior by editing the python script itself.  There is a line at the top:
`complete_vgmaps_default = False`
which you can change to 
`complete_vgmaps_default = True`
This will also change the command line argument `-c, --completemaps` into `-p, --partialmaps` which you would call to enable non-empty group vgmaps instead.

### kuro_mdl_import_meshes.py
Double click the python script and it will search the current folder for all .mdl files with exported folders, and import the meshes in the folder back into the mdl file.  Additionally, it will parse the 4 JSON files (mesh metadata, materials, skeleton and MDL version) if available and use that information to rebuild the mesh, materials and skeleton sections.  This script requires a working mdl file already be present as it does not reconstruct the entire file; only the known relevant sections.  The remaining parts of the file (any animation data, etc) are copied unaltered from the intact mdl file.  By default, it will apply zstandard compression to the final file if the original file is compressed.

It will make a backup of the original, then overwrite the original.  It will not overwrite backups; for example if "model.mdl.bak" already exists, then it will write the backup to "model.mdl.bak1", then to "model.mdl.bak2", and so on.

**Command line arguments:**
`kuro_mdl_import_meshes.py [-h] [-c] [-f] mdl_filename`

`-h, --help`
Shows help message.

`-c, --change_compression`
By default, the import script will detect if the current (pre-import) mdl file has CLE zstandard compression applied, and will compress the new file only if the current file is compressed.  Using this option will force the script to change the compression (*e.g.* it will change the output from compressed to non-compressed, or from non-compressed to compressed).

`-f {1,2}, --force_version {1,2}`
This option will tell the importer to force compile the MDL at a specific Kuro version.  At this time, it only supports downgrading Kuro 2 MDLs to Kuro 1.  Hopefully in the future we will know enough about the new version to allow upgrading as well.  Of note, when missing / invalid submeshes are detected, K1 behavior is to completely remove the entry from the MDL (needed for NISA Kuro 1), and K2 behavior is to insert a dummy (invisible) submesh (needed for CLE Kuro 2).

**Adding and deleting meshes**

If meshes are missing (.fmt/.ib/.vb files that have been deleted), then the script will insert an empty (invisible) mesh in its place.  Metadata does not need to be altered.

The script only looks for mesh files that are listed in the JSON file.  If you want to add a new mesh, you will need to add metadata.  My script only reads the "material" entry, everything else is automatically generated.  So a section added to the end of the "primitives" section like this will be sufficient:
```
            {
                "material": "c03_metal",
            }
```
Be sure to add a comma to the } for the section prior if you are using a text editor, or better yet use a dedicated JSON editor.  I actually recommend editing JSON in a dedicated editor, because python is not forgiving if you make mistakes with the JSON structure.  (Try https://jsoneditoronline.org)  Also, be sure to point material to a real section in material_info.json.  You might want to create a new section, or use an existing one.

**Changing textures**

First look inside mesh_info.json and find the mesh you want to edit.  Identify the group, then look inside primitives.  For example, if you want to edit the metadata for "2_woman01_body79_05.vb" then it will be inside group 2 (which is the 3rd group, 0 is the first), named "woman01_body79."  Inside "primitives" you will find mesh 5 (which is the 6th mesh, 0 is the first).  It will say "id_referenceonly": "5".  Under id_referenceonly is material.  That is the material entry you need to alter.

Go to material_info.json, and go that section.  For example, if "material" in mesh_info was "hair", then go to the section of material_info.json with the tag ```"material_name": "hair"```.  Under textures, you can change the file names.  When changing the texture filenames, do not put ".dds".

*Notes:*
- All the changes should be in material_info.json.  There is nothing worth changing in mesh_info.json.
- When making mods with new textures, I highly recommend giving them unique names, instead of asking the user to overwrite textures that already exist.  That way, you do not have to worry about when two or more models use the same textures.  You should be able to add new texture slots or delete old ones as well (for example adding normal or gradient maps to meshes that did not have them before), just carefully copy from other meshes.  *Kuro 2 requires that the new textures have the same filename length as the original textures.*
- The textures that come with the CLE release are compressed.  Use cle_decrypt_decompress.py.  Kuro 1 will read uncompressed dds files; Kuro 2 will crash with uncompressed dds files.  Use cle_compress.py to compress the texture files before use.

**Changing shaders**

Please see the instructions above for changing textures.  We cannot create novel configurations of shaders, because they are already compiled in pre-determined configurations.  To create a new material, you must base it off of a valid configuration.  Copy the entire section from the model you want, and give it a unique "material_name".  *Do not change anything in "shader_name", "str3", or "material_switches" - if you need different switches then find an existing material with the switches that you need.*  Update the textures section as above to point to your textures.  The values for the "parameters" section can be changed, but you cannot add or remove the parameters themselves.  (For example, if your material has "rimLightColor_g" set to [0.627, 0.558, 0.504], you can change that value.  But if the material does not have "rimLightColor_g" at all, you cannot at it.  Nor can you remove the parameter entirely if you do not want rim lighting, for example.  Also, I do not believe you can change values for parameters that start with "Switch_".)

*Notes:*
- All the changes should be in material_info.json.  There is nothing worth changing in mesh_info.json.
- Changing shaders in CLE 2 Kuro results in crashes.

**Changing the skeleton**

I do not recommend directly editing skeleton.json, although it certainly is possible (assuming you know how to do matrix math).  It is better to generate a glTF file (see below), import into Blender using Bone Dir "Blender (best for re-importing)", and edit the skeleton there.  *Do not use the default Bone Dir setting, "Temperance (Average)", if you intend to export the skeleton!*  Export as .glb, update the associated .metadata, then run kuro_gltf_to_meshes.py to extract your .glb model to meshes/json.  This will extract your new skeleton, along with new bone palettes and their associated bind matrices.

### kuro_mdl_to_basic_gltf.py
Double click the python script to run and it will attempt to convert the MDL model into a basic glTF model, with skeleton (in .glb format).  This tool as written is for obtaining the skeleton for rigging the .fmt/.ib/.vb/.vgmap meshes from the export tool.  *The meshes included in the model are not particularly useful as they cannot be exported back to MDL,* just delete them and import the exported meshes (.fmt/.ib/.vb./vgmap) instead - the tool only includes meshes because Blender refuses to open a glTF file without meshes.  After importing the meshes, Ctrl-click on the armature and parent (Object -> Parent -> Armature Deform {without the extra options}).

The script has basic texture support.  Place all the textures required in the same folder as the .glb file, in .dds format.  Blender does not support BC7 textures, so convert to BC1/BC3 first.

Animations will also be converted into glTF (in .glb format).  The glb files can be directly imported into Blender, but Bone Dir must be set to "Blender (best for re-importing)" upon import or the skeleton will be altered irreversibly, preventing the animation from being used in the game.  (Repacking animations is not yet supported.)  Using the files directly is not recommended; instead decompile the base model as well, and put the .glb file in the same folder with the animations and run kuro_merge_model_into_animations.py in that folder. It will insert the model data including meshes / skins / texture references etc into the animation .glb, which will make animation feasible.  This tool only supports translation, rotation and scale animation channels.  *If you run this tool on an animation that exclusively utilizes the shader varying or uv scrolling channels, you will end up with an empty .glb.  You can examine the unsupported channels in json format using the --dumpanidata command.*

It will search the current folder for mdl files and convert them all, unless you use command line options.

**Command line arguments:**
`kuro_mdl_to_basic_gltf.py [-h] [-o] [-t] [-d] [-c] mdl_filename`

`-h, --help`
Shows help message.

`-o, --overwrite`
Overwrite existing files without prompting.

`-t, --textformat`
Output .gltf/.bin format instead of .glb format.

`-d, --dumpanidata`
Dump all animation data (including unused channels and unknown floats) and the skeleton into .json files.  (Can be used with kuro_mdl_import_animation.py to allow manual changes to animation data.  This is mainly intended for use in modifying UV scrolling and shader parameter varying keyframes.)

`-p, --preserve_bind_matrices`
Use the bind matrices already in the mdl file, instead of calculating inverse bind matrices for each skinned mesh which is the default behavior.  This can do strange things to the models / animations, but may be necessary in some situations.

### kuro_merge_model_into_animations.py
Double click the python script to run, and it will attempt to merge each animation it finds with its base model.  Animations are detected as .glb (or .gltf) files with underscores in their names, and the base model is the prefix before the first underscore.  For example, if it finds chr5001_mot_walk.glb, it will attempt to merge into it chr5001.glb.  The original animation .glb will be overwritten with the merged animation .glb.  This tool only supports translation, rotation and scale animation channels.

*Note that it will first search for a model .glb with the basename; if it does not find one, it will try to find a costume.  For example, if chr5001.glb is not available, it will look for files such as chr5001_c03.glb and use the first one that it finds.

**Command line arguments:**
`kuro_merge_model_into_animations.py [-h] [-k] model_filename animation_filename`

`-h, --help`
Shows help message.

`-k, --keep_model_ani`
Default behavior is to discard the animation that is in the model glTF, and replace it with the animation in the animation glTF.  Using this option will instead have the script append the animation.  Blender does not support multiple glTF animations so for Blender this option should not be used.  Also, this option will not work with kuro_mdl_import_animation.py.

### kuro_mdl_import_animation.py
Double click the python script and it will search the current folder for all .mdl files with exported gltf/glb files and animations within the .mdl file, and import the animation (and skeleton) from the gltf/glb file back into the mdl file.  Additionally, it will parse the .metadata JSON file if available and use that information to properly rebuild the skeleton section.  This script requires a working mdl file already be present as it does not reconstruct the entire file; only the known relevant sections.  The remaining parts of the file (any mesh or material data, etc) are copied unaltered from the intact mdl file.  By default, it will apply zstandard compression to the final file if the original file is compressed.  This tool only supports translation, rotation and scale animation channels.

Note that both kuro_mdl_import_meshes.py and kuro_mdl_import_animation.py will overwrite the skeleton.  For mdl files that have both model and animation data, I recommend running kuro_mdl_import_meshes.py first, then kuro_mdl_import_animation.py second, because Kuro calculates animation keyframes off the skeleton so they must be properly paired.  Be absolutely sure that the model is compatible with the skeleton from the animation.

It will make a backup of the original, then overwrite the original.  It will not overwrite backups; for example if "model.mdl.bak" already exists, then it will write the backup to "model.mdl.bak1", then to "model.mdl.bak2", and so on.

*Note: Animations in MDL version 2 format are auto-downgraded to version 1, as v2 custom animations in CLE Kuro 2 are not able to pass the startup check and result in the infamous endless load screen.  This script can only auto-downgrade pure animations, not model+animation mdls.  For the latter, use kuro_mdl_export_meshes.py / kuro_mdl_import_meshes.py and manually downgrade the .mdl before importing the animation.*

**Command line arguments:**
`kuro_mdl_import_animation.py [-h] [-c] mdl_filename`

`-h, --help`
Shows help message.

`-c, --change_compression`
By default, the import script will detect if the current (pre-import) mdl file has CLE zstandard compression applied, and will compress the new file only if the current file is compressed.  Using this option will force the script to change the compression (*e.g.* it will change the output from compressed to non-compressed, or from non-compressed to compressed).

`-j, --use_json_data`
This option will direct the script to read the skeleton and all animation data from JSON files instead of a glTF container.  The script expects output from kuro_mdl_to_basic_gltf.py invoked with the -d option.

### kuro_gltf_to_meshes.py
Double click the python script to run, and it will attempt to pull the meshes, skeleton and bone palettes out of each glTF file it finds (.glb or .gltf).  It will write to the same folder that kuro_mdl_export_meshes.py writes to.  This is very experimental, and it can only output in MDL v1 format (i.e. for Kuro 1, although CLE Kuro 2 accepts MDL v1 files).  It does not output materials, so use the material_info.json from kuro_mdl_export_meshes.py.

**Command line arguments:**
`kuro_gltf_to_meshes.py [-h] [-c] [-o] mdl_filename`

`-h, --help`
Shows help message.

`-c, --completemaps`
.vgmap files will have the entire skeleton, with every bone available to the mesh, included with each mesh.  This will result in many empty vertex groups upon import into Blender.  The default behavior is to only include vertex groups that contain at least one vertex.  Complete maps are primarily useful when merging one mesh into another.

`-o, --overwrite`
Overwrite existing files without prompting.

**Complete VGMap Setting:**

Many modders prefer that complete VGmaps is the default, rather than a command line option.  You can (permanently) change the default behavior by editing the python script itself.  There is a line at the top:
`complete_vgmaps_default = False`
which you can change to 
`complete_vgmaps_default = True`
This will also change the command line argument `-c, --completemaps` into `-p, --partialmaps` which you would call to enable non-empty group vgmaps instead.

### cle_compress.py
This script will compress files with zstandard so they can be used in Kuro no Kiseki 2 (CLE release).  If double-clicked, it will compress all files it finds in the current directory, assuming they are not .py, .bak, or already compressed.  This is not necessary with output from the importer since the files are already compressed, but would be needed for textures, etc.

**Command line arguments:**
`cle_compress.py [-h] filename`

No command line options, but you can compress single files using the command line.

### cle_decrypt_decompress.py
This script will decrypt and/or decompress files using the Blowfish key that is used in Kuro no Kiseki 1 / 2 (CLE release).  If double-clicked, it will decrypt and decompress all files it finds in the current directory, assuming they are not .original_encrypted files.  It will make a backup copy of the original with .original_encrypted extension appended to the name.

**Command line arguments:**
`cle_decrypt_decompress.py [-h] cle_asset_filename`

No command line options, but you can decrypt / decompress single files using the command line.
