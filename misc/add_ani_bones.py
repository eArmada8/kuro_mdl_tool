# Tool to push bones / keyframes from one gltf animation into another.  A companion to kuro_mdl_to_basic_gltf.py.
#
# GitHub eArmada8/kuro_mdl_tool

try:
    import glob, copy, os, struct, numpy, io, sys
    from pygltflib import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

def read_gltf_stream (gltf, accessor_num):
    accessor = gltf.accessors[accessor_num]
    bufferview = gltf.bufferViews[accessor.bufferView]
    buffer = gltf.buffers[bufferview.buffer]
    componentType = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}
    componentSize = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    componentCount = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}
    componentFormat = "<{0}{1}".format(componentCount[accessor.type],\
        componentType[accessor.componentType])
    componentStride = componentCount[accessor.type] * componentSize[accessor.componentType]
    data = []
    with io.BytesIO(gltf.get_data_from_buffer_uri(buffer.uri)) as f:
        f.seek(bufferview.byteOffset + accessor.byteOffset, 0)
        for i in range(accessor.count):
            data.append(list(struct.unpack(componentFormat, f.read(componentStride))))
            if (bufferview.byteStride is not None) and (bufferview.byteStride > componentStride):
                f.seek(bufferview.byteStride - componentStride, 1)
    if accessor.normalized == True:
        for i in range(len(data)):
            if componentType == 'b':
                data[i] = [x / ((2**(8-1))-1) for x in data[i]]
            elif componentType == 'B':
                data[i] = [x / ((2**8)-1) for x in data[i]]
            elif componentType == 'h':
                data[i] = [x / ((2**(16-1))-1) for x in data[i]]
            elif componentType == 'H':
                data[i] = [x / ((2**16)-1) for x in data[i]]
    return(data)

def attach_bones_and_animation(donor_gltf, recipient_gltf, root_bone_list = [], targets = ['translation', 'rotation', 'scale'], fix_start = True, fix_length = True):
    def build_bone_list (bone_list, bone_id, gltf):
        if bone_id < len(donor_gltf.nodes) and not donor_gltf.nodes[bone_id].name in bone_list:
            bone_list.append(donor_gltf.nodes[bone_id].name)
            for i in range(len(donor_gltf.nodes[bone_id].children)):
                bone_list = build_bone_list(bone_list, donor_gltf.nodes[bone_id].children[i], gltf)
        return(bone_list)
    def get_parent_id (bone, gltf):
        bones = [x.name for x in gltf.nodes]
        if bone in bones:
            bone_id = [i for i in range(len(gltf.nodes)) if gltf.nodes[i].name == bone][0]
            parent_list = [i for i in range(len(gltf.nodes)) if gltf.nodes[i].children is not None and bone_id in gltf.nodes[i].children]
            if len(parent_list) > 0:
                return parent_list[0]
        return False
    bone_list = []
    for i in range(len(root_bone_list)):
        bone_ids = [j for j in range(len(donor_gltf.nodes)) if donor_gltf.nodes[j].name == root_bone_list[i]]
        parent_id = get_parent_id(root_bone_list[i],donor_gltf)
        if len(bone_ids) > 0 and parent_id is not False and donor_gltf.nodes[parent_id].name in [x.name for x in recipient_gltf.nodes]:
            bone_list.extend(build_bone_list([], bone_ids[0], donor_gltf))
    for i in range(len(bone_list)):
        parent = [j for j in range(len(recipient_gltf.nodes)) if recipient_gltf.nodes[j].name == donor_gltf.nodes[get_parent_id(bone_list[i],donor_gltf)].name][0]
        if len([j for j in range(len(donor_gltf.nodes)) if donor_gltf.nodes[j].name == bone_list[i]]) > 0:
            new_node = copy.deepcopy(donor_gltf.nodes[[j for j in range(len(donor_gltf.nodes)) if donor_gltf.nodes[j].name == bone_list[i]][0]])
            new_node.children = []
            recipient_gltf.nodes[parent].children.append(len(recipient_gltf.nodes))
            recipient_gltf.nodes.append(new_node)
    if len(recipient_gltf.animations) > 0 and len(donor_gltf.animations) > 0:
        recipient_gltf.convert_buffers(BufferFormat.BINARYBLOB)
        binary_blob = recipient_gltf.binary_blob()
        blob_len = len(binary_blob)
        animation = recipient_gltf.animations[0]
        rec_start = min([x for y in recipient_gltf.animations[0].samplers for x in recipient_gltf.accessors[y.input].min])
        rec_end = max([x for y in recipient_gltf.animations[0].samplers for x in recipient_gltf.accessors[y.input].max])
        don_start = min([x for y in donor_gltf.animations[0].samplers for x in donor_gltf.accessors[y.input].min])
        don_end = max([x for y in donor_gltf.animations[0].samplers for x in donor_gltf.accessors[y.input].max])
        offset = rec_start - don_start
        time_skew = (rec_end - rec_start) / (don_end - don_start)
        if offset != 0.0:
            print("Warning! Starting times do not match!  Will adjust start time: {}".format(fix_start))
        if time_skew != 1.0:
            print("Warning! Animation lengths do not match!  Will adjust animation length: {}".format(fix_length))
        for j in range(len(donor_gltf.animations[0].channels)):
            sampler_input_acc = donor_gltf.animations[0].samplers[donor_gltf.animations[0].channels[j].sampler].input
            sampler_input = read_gltf_stream(donor_gltf, sampler_input_acc)
            if time_skew != 1.0 and fix_length == True:
                sampler_input = [[(x-don_start)*time_skew+don_start] for y in sampler_input for x in y]
            if offset != 0.0 and fix_start == True:
                sampler_input = [[x+offset] for y in sampler_input for x in y]
            sampler_output_acc = donor_gltf.animations[0].samplers[donor_gltf.animations[0].channels[j].sampler].output
            sampler_output = read_gltf_stream(donor_gltf, sampler_output_acc)
            sampler_interpolation = donor_gltf.animations[0].samplers[donor_gltf.animations[0].channels[j].sampler].interpolation
            target_path = donor_gltf.animations[0].channels[j].target.path
            target_node_name = donor_gltf.nodes[donor_gltf.animations[0].channels[j].target.node].name
            if target_node_name in bone_list and target_path in targets:
                target_node = [k for k in range(len(recipient_gltf.nodes)) if recipient_gltf.nodes[k].name == target_node_name][0]
                ani_sampler = AnimationSampler()
                blobdata = numpy.array(sampler_input,dtype="float32").tobytes()
                bufferview = BufferView()
                bufferview.buffer = 0
                bufferview.byteOffset = len(binary_blob)
                bufferview.byteLength = len(blobdata)
                binary_blob += blobdata
                padding_length = 4 - len(blobdata) % 4
                binary_blob += b'\x00' * padding_length
                accessor = Accessor()
                accessor.bufferView = len(recipient_gltf.bufferViews)
                accessor.componentType = 5126
                accessor.type = {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[len(sampler_input[0])]
                accessor.count = len(sampler_input)
                accessor.min = min(sampler_input)
                accessor.max = max(sampler_input)
                ani_sampler.input = len(recipient_gltf.accessors)
                recipient_gltf.accessors.append(accessor)
                recipient_gltf.bufferViews.append(bufferview)
                blobdata = numpy.array(sampler_output,dtype="float32").tobytes()
                bufferview = BufferView()
                bufferview.buffer = 0
                bufferview.byteOffset = len(binary_blob)
                bufferview.byteLength = len(blobdata)
                binary_blob += blobdata
                padding_length = 4 - len(blobdata) % 4
                binary_blob += b'\x00' * padding_length
                accessor = Accessor()
                accessor.bufferView = len(recipient_gltf.bufferViews)
                accessor.componentType = 5126
                accessor.type = {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[len(sampler_output[0])]
                accessor.count = len(sampler_input)
                ani_sampler.output = len(recipient_gltf.accessors)
                recipient_gltf.accessors.append(accessor)
                recipient_gltf.bufferViews.append(bufferview)
                ani_sampler.interpolation = sampler_interpolation
                ani_channel = AnimationChannel()
                ani_channel.sampler = len(animation.samplers)
                ani_channel.target = AnimationChannelTarget()
                ani_channel.target.path = target_path
                ani_channel.target.node = target_node
                animation.samplers.append(ani_sampler)
                animation.channels.append(ani_channel)
        recipient_gltf.buffers[0].byteLength = len(binary_blob)
        recipient_gltf.set_binary_blob(binary_blob)
    return(recipient_gltf)

def process_animations(donor_filename, recipient_filename, root_bone_list = [], targets = ['translation', 'rotation', 'scale'], fix_start = True, fix_length = True):
    print("Processing {0} -> {1}...".format(donor_filename, recipient_filename))
    donor_gltf = GLTF2().load(donor_filename)
    recipient_gltf = GLTF2.load(recipient_filename)
    recipient_gltf.save(recipient_filename.split('.gl')[0]+'_original.glb')
    recipient_gltf = attach_bones_and_animation(donor_gltf, recipient_gltf, root_bone_list = root_bone_list, targets = targets, fix_start = fix_start, fix_length = fix_length)
    recipient_gltf.save(recipient_filename)

if __name__ == '__main__':
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--add_bone', action='append', help="Name of bone to add (required, can call more than once)", required=True)
    parser.add_argument('-s', '--do_not_fix_start_time', help="Preserve original start time", action="store_false")
    parser.add_argument('-l', '--do_not_fix_length', help="Preserve original length", action="store_false")
    parser.add_argument('donor_filename', help="Name of glTF file obtain bones and animations from (required).")
    parser.add_argument('recipient_filename', help="Name of glTF file to add bones and animations to (required).")
    args = parser.parse_args()
    if os.path.exists(args.donor_filename) and os.path.exists(args.recipient_filename):
        process_animations(args.donor_filename, args.recipient_filename, args.add_bone, ['rotation'], fix_start = args.do_not_fix_start_time, fix_length = args.do_not_fix_length)
