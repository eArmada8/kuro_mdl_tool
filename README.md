# Kuro MDL mesh export and import
A pair of scripts to get the mesh data out of MDL files and back into MDL files.  The output is in .fmt/.vb/.ib files that are compatible with DarkStarSword Blender import plugin for 3DMigoto, and metadata is in JSON format.

## Credits:
99.9% of my understanding of the MDL format comes from the reverse engineering work of Julian Uy (github.com/uyjulian), and specifically his MDL to GLTF convertor: https://gist.github.com/uyjulian/9a9d6395682dac55d113b503b1172009

The code to decrypt and decompress CLE assets comes from KuroTools (https://github.com/nnguyen259/KuroTools), and I also looked through MDL convertor in KuroTools by TwnKey (github.com/TwnKey) to understand the MDL format.

None of this would be possible without the work of DarkStarSword and his amazing 3DMigoto-Blender plugin, of course.

I am very thankful for uyjulian, TwnKey, DarkStarSword, the KuroTools team and the Kiseki modding discord for their brilliant work and for sharing that work so freely.

## Requirements:
1. Python 3.10 and newer is required for use of these scripts.  It is free from the Microsoft Store, for Windows users.  For Linux users, please consult your distro.
2. The blowfish and zstandard modules for python are needed.  Install by typing "python3 -m pip install blowfish zstandard" in the command line / shell.  (The io, re, struct, sys, os, shutil, glob, base64, json, operator, argparse and itertools modules are also required, but these are all already included in most basic python installations.)
3. The output can be imported into Blender using DarkStarSword's amazing plugin: https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py
4. kuro_mdl_export_meshes.py is dependent on lib_fmtibvb.py, which must be in the same folder.  
kuro_mdl_import_meshes.py is dependent on both kuro_mdl_export_meshes.py and lib_fmtibvb.py.

## Usage:
### kuro_mdl_export_meshes.py
Double click the python script and it will search the current folder for all .mdl files and export the meshes into a folder with the same name as the mdl file.  Additionally, it will output 2 JSON files, one with metadata from the mesh section, and another with the data from the materials section.

**Command line arguments:**
`kuro_mdl_export_meshes.py [-h] [-c] [-t] [-o] mdl_filename`

`-h, --help`
Shows help message.

`-c, --completemaps`
.vgmap files will have the entire skeleton, with every bone available to the mesh, included with each mesh.  This will result in many empty vertex groups upon import into Blender.  The default behavior is to only include vertex groups that contain at least one vertex.  Complete maps are primarily useful when merging one mesh into another.

`-t, --trim_for_gpu`
Trim vertex buffer for GPU injection (3DMigoto).  Meshes in the MDL contain have 15 vertex buffers (position, normal, tangent, 8x texcoord, 2x unknown, blendweights and blendindices).  Only 8 of these are actually loaded into GPU memory (only the first 3 texcoords are loaded, and the 2x unknown are not loaded).  This option produces smaller .vb files (with matching .fmt files) with the extraneous buffers discarded, so that upon splitting, the buffers can be used for injection with 3DMigoto.  (See here for my vertex buffer splitting tool: https://github.com/eArmada8/vbuffer_merge_split/blob/main/kuro/kuro_vb_split.py)

`-o, --overwrite`
Overwrite existing files without prompting.

### kuro_mdl_import_meshes.py
Double click the python script and it will search the current folder for all .mdl files with exported folders, and import the meshes in the folder back into the mdl file.  Additionally, it will parse the 2 JSON files (mesh metadata and materials) if available and use that information to rebuild the mesh and materials sections.  This script requires a working mdl file already be present as it does not reconstruct the entire file; only the known relevant sections.  The remaining parts of the file (bone heirarchy, any animation data, etc) are copied unaltered from the intact mdl file.

It will make a backup of the original, then overwrite the original.  It will not overwrite backups; for example if "model.mdl.bak" already exists, then it will write the backup to "model.mdl.bak1", then to "model.mdl.bak2", and so on.

**Command line arguments:**
`kuro_mdl_import_meshes.py [-h] mdl_filename`

`-h, --help`
Shows help message.
