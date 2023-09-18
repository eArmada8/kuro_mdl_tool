# Tool to push a gltf model into animations.  A companion to ed8pkg2gltf.py.
#
# GitHub eArmada8/ed8pkg2gltf

try:
    import glob, os, json, struct, numpy, io, sys
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

def apply_animations_to_model_gltf (model_gltf, ani_gltf):
    # Apply animation pose to model
    for i in range(len(model_gltf.nodes)):
        if model_gltf.nodes[i].name in [x.name for x in ani_gltf.nodes]:
            ani_node = [j for j in range(len(ani_gltf.nodes)) if ani_gltf.nodes[j].name == model_gltf.nodes[i].name][0]
            for key in ['matrix', 'translation', 'rotation', 'scale']:
                if getattr(model_gltf.nodes[i], key) is not None:
                    setattr(model_gltf.nodes[i], key, None)
                if getattr(ani_gltf.nodes[ani_node], key) is not None:
                    setattr(model_gltf.nodes[i], key, getattr(ani_gltf.nodes[ani_node], key))
    # Copy animations into model
    model_gltf.convert_buffers(BufferFormat.BINARYBLOB)
    binary_blob = model_gltf.binary_blob()
    blob_len = len(model_gltf.binary_blob())
    for i in range(len(ani_gltf.animations)):
        animation = Animation()
        for j in range(len(ani_gltf.animations[i].channels)):
            sampler_input_acc = ani_gltf.animations[i].samplers[ani_gltf.animations[i].channels[j].sampler].input
            sampler_input = read_gltf_stream(ani_gltf, sampler_input_acc)
            sampler_output_acc = ani_gltf.animations[i].samplers[ani_gltf.animations[i].channels[j].sampler].output
            sampler_output = read_gltf_stream(ani_gltf, sampler_output_acc)
            sampler_interpolation = ani_gltf.animations[i].samplers[ani_gltf.animations[i].channels[j].sampler].interpolation
            target_path = ani_gltf.animations[i].channels[j].target.path
            target_node_name = ani_gltf.nodes[ani_gltf.animations[i].channels[j].target.node].name
            if target_node_name in [x.name for x in model_gltf.nodes]:
                target_node = [k for k in range(len(model_gltf.nodes)) if model_gltf.nodes[k].name == target_node_name][0]
                ani_sampler = AnimationSampler()
                blobdata = numpy.array(sampler_input,dtype="float32").tobytes()
                bufferview = BufferView()
                bufferview.buffer = 0
                bufferview.byteOffset = blob_len
                bufferview.byteLength = len(blobdata)
                binary_blob += blobdata
                blob_len += len(blobdata)
                padding_length = 4 - len(blobdata) % 4
                binary_blob += b'\x00' * padding_length
                blob_len += padding_length      
                accessor = Accessor()
                accessor.bufferView = len(model_gltf.bufferViews)
                accessor.componentType = 5126
                accessor.type = {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[len(sampler_input[0])]
                accessor.count = len(sampler_input)
                accessor.min = min(sampler_input)
                accessor.max = max(sampler_input)
                ani_sampler.input = len(model_gltf.accessors)
                model_gltf.accessors.append(accessor)
                model_gltf.bufferViews.append(bufferview)
                blobdata = numpy.array(sampler_output,dtype="float32").tobytes()
                bufferview = BufferView()
                bufferview.buffer = 0
                bufferview.byteOffset = blob_len
                bufferview.byteLength = len(blobdata)
                binary_blob += blobdata
                blob_len += len(blobdata)
                padding_length = 4 - len(blobdata) % 4
                binary_blob += b'\x00' * padding_length
                blob_len += padding_length      
                accessor = Accessor()
                accessor.bufferView = len(model_gltf.bufferViews)
                accessor.componentType = 5126
                accessor.type = {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[len(sampler_output[0])]
                accessor.count = len(sampler_input)
                ani_sampler.output = len(model_gltf.accessors)
                model_gltf.accessors.append(accessor)
                model_gltf.bufferViews.append(bufferview)
                ani_sampler.interpolation = sampler_interpolation
                ani_channel = AnimationChannel()
                ani_channel.sampler = len(animation.samplers)
                ani_channel.target = AnimationChannelTarget()
                ani_channel.target.path = target_path
                ani_channel.target.node = target_node
                animation.samplers.append(ani_sampler)
                animation.channels.append(ani_channel)
        model_gltf.animations.append(animation)
    model_gltf.buffers[0].byteLength = blob_len
    model_gltf.set_binary_blob(binary_blob)
    return(model_gltf)

def process_animation (animation):
    print("Processing {0}...".format(animation))
    if os.path.exists(animation+'.gltf'):
        ani_filename = animation+'.gltf'
        output = 'GLTF'
    elif os.path.exists(animation+'.glb'):
        ani_filename = animation+'.glb'
        output = 'GLB'
    else:
        print("Animation {} not found, skipping...".format(animation))
        return False
    ani_gltf = GLTF2().load(ani_filename)
    if len(ani_filename.split('_')) > 1:
        model_filename = ani_filename.split('_')[0]
        if os.path.exists(model_filename+'.glb'):
            model_gltf = GLTF2.load(model_filename+'.glb')
        elif os.path.exists(model_filename+'.gltf'):
            model_gltf = GLTF2.load(model_filename+'.gltf')
        else:
            print("Model {0}.glb/.gltf not found, skipping animation {1}...".format(model_filename, animation))
            return False
        new_model = apply_animations_to_model_gltf (model_gltf, ani_gltf)
        new_model.convert_buffers(BufferFormat.BINARYBLOB)
        if output == 'GLB':
            new_model.save_binary("{}.glb".format(animation))
            return True
        else:
            new_model.save("{}.gltf".format(animation))
            return True

if __name__ == '__main__':
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
    animations = [x.split('.gl')[0] for x in glob.glob("*.gl*") if len(x.split('_')) > 1]
    for animation in animations:
        process_animation(animation)
