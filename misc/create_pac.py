# Tool to create .pac files for Trails in the Sky 1st Chapter
# Thank you to the folks at the Kiseki Modding Discord who
# reverse engineered this format!
#
# GitHub eArmada8/kuro_mdl_tool

try:
    import struct, zlib, glob, os, sys
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

def pac_pack_files (assigned_paths):
    hashes = {x : zlib.crc32(x.encode("utf8")) ^ 0xFFFFFFFF for x in assigned_paths}
    hash_order = sorted(list(hashes.values()))
    header1_size = len(assigned_paths) * 0x20 + 0x10
    header2_size = sum([len(x)+1 for x in assigned_paths])
    header1_struct = {}
    header1, header2, data_block = bytearray(), bytearray(), bytearray()
    for i in range(len(assigned_paths)):
        file_data = open(assigned_paths[i], 'rb').read()
        header1_struct[hashes[assigned_paths[i]]] = struct.pack("<2I3Q", hashes[assigned_paths[i]], 0,
            header1_size + len(header2),
            len(file_data),
            header1_size + header2_size + len(data_block))
        header2.extend(assigned_paths[i].encode("utf8") + b'\x00')
        data_block.extend(file_data)
    for i in range(len(hash_order)):
        header1.extend(header1_struct[hash_order[i]])
    return(b'FPAC' + struct.pack("<3I", len(assigned_paths), (len(header1) + len(header2) + 0x10), 1) +
        header1 + header2 + data_block)

def pack_folder (folder_name, output_name = None, overwrite = False):
    if output_name == None:
        pac_name = folder_name + '.pac'
    else:
        pac_name = "".join([x if x not in "\/:*?<>|" else "_" for x in output_name]) #Sanitize
        if not pac_name.lower()[-4:] == '.pac':
            pac_name = pac_name + '.pac'
    if os.path.exists(pac_name) and overwrite == False:
        if str(input(pac_name + " exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
            overwrite = True
    if (overwrite == True) or not os.path.exists(pac_name):
        file_list = [x.replace('\\','/') for x in glob.glob('**/*',root_dir=folder_name,recursive=True)
            if not os.path.isdir(folder_name+'/'+x)]
        assigned_paths = [folder_name+'/'+x for x in file_list]
        pac_data = pac_pack_files (assigned_paths)
        with open(pac_name, 'wb') as f:
            f.write(pac_data)
    return

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to export from file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('folder_name', help="Name of folder to compress (required).")
        parser.add_argument('-a', '--output_name', help="Name of output pac file (optional)", default=None)
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        args = parser.parse_args()
        if os.path.exists(os.path.basename(args.folder_name)):
            pack_folder(os.path.basename(args.folder_name), args.output_name, overwrite = args.overwrite)
    else:
        all_folders = [x for x in glob.glob('*', recursive = False) if os.path.isdir(x)]
        all_folders = [x for x in all_folders if x != '__pycache__']
        for i in range(len(all_folders)):
            pack_folder(all_folders[i])