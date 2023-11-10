# Tool to push a gltf model into animations.  A companion to kuro_mdl_to_basic_gltf.py.
#
# GitHub eArmada8/kuro_mdl_tool

try:
    import glob, os, json, struct, numpy, io, sys
    from lib_fmtibvb import *
    from pygltflib import *
    from pyquaternion import Quaternion
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

# Set to True to prevent overwriting the model bind pose with the animation pose
preserve_translation = False
preserve_rotation = False
preserve_scale = False
# If True, locators will be transformed regardless of above.  Nodes in always_transform_nodes will always be applied. 
always_transform_locators = True
always_transform_nodes = ['Up_Point']

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

def apply_animations_to_model_gltf (model_gltf, ani_gltf, locators, remove_model_ani = True):
    global preserve_translation, preserve_rotation, preserve_scale
    global always_transform_locators, always_transform_nodes

    transformed_model = False # To detect animations not affected by model (e.g. S-craft cameras)
    # Apply animation pose to model
    for i in range(len(model_gltf.nodes)):
        if model_gltf.nodes[i].name in [x.name for x in ani_gltf.nodes]:
            ani_node = [j for j in range(len(ani_gltf.nodes)) if ani_gltf.nodes[j].name == model_gltf.nodes[i].name][0]
            # Model (bind) pose
            if model_gltf.nodes[i].matrix is not None:
                model_s = [numpy.linalg.norm(model_gltf.nodes[i].matrix[0:3]), numpy.linalg.norm(model_gltf.nodes[i].matrix[4:7]),\
                    numpy.linalg.norm(model_gltf.nodes[i].matrix[8:11])]
                t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],model_gltf.nodes[i].matrix[12:15]+[1]]).transpose()
                r_mtx = numpy.array([(model_gltf.nodes[i].matrix[0:3]/model_s[0]).tolist()+[0],\
                    (model_gltf.nodes[i].matrix[4:7]/model_s[1]).tolist()+[0],\
                    (model_gltf.nodes[i].matrix[8:11]/model_s[2]).tolist()+[0],[0,0,0,1]]).transpose()
                s_mtx = numpy.array([[model_s[0],0,0,0],[0,model_s[1],0,0],[0,0,model_s[2],0],[0,0,0,1]])
            else:
                if model_gltf.nodes[i].translation is not None:
                    t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],model_gltf.nodes[i].translation+[1]]).transpose()
                else:
                    t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
                if model_gltf.nodes[i].rotation is not None:
                    r_mtx = Quaternion(model_gltf.nodes[i].rotation[3], model_gltf.nodes[i].rotation[0],\
                        model_gltf.nodes[i].rotation[1], model_gltf.nodes[i].rotation[2]).transformation_matrix
                else:
                    r_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
                if model_gltf.nodes[i].scale is not None:
                    s_mtx = numpy.array([[model_gltf.nodes[i].scale[0],0,0,0],\
                        [0,model_gltf.nodes[i].scale[1],0,0],[0,0,model_gltf.nodes[i].scale[2],0],[0,0,0,1]])
                else:
                    s_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
            # Animation pose
            if ani_gltf.nodes[ani_node].matrix is not None:
                anipose_s = [numpy.linalg.norm(ani_gltf.nodes[ani_node].matrix[0:3]), numpy.linalg.norm(ani_gltf.nodes[ani_node].matrix[4:7]),\
                    numpy.linalg.norm(ani_gltf.nodes[ani_node].matrix[8:11])]
                anipose_t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],ani_gltf.nodes[ani_node].matrix[12:15]+[1]]).transpose()
                anipose_r_mtx = numpy.array([(ani_gltf.nodes[ani_node].matrix[0:3]/anipose_s[0]).tolist()+[0],\
                    (ani_gltf.nodes[ani_node].matrix[4:7]/anipose_s[1]).tolist()+[0],\
                    (ani_gltf.nodes[ani_node].matrix[8:11]/anipose_s[2]).tolist()+[0],[0,0,0,1]]).transpose()
                anipose_s_mtx = numpy.array([[anipose_s[0],0,0,0],[0,anipose_s[1],0,0],[0,0,anipose_s[2],0],[0,0,0,1]])
            else:
                if ani_gltf.nodes[ani_node].translation is not None:
                    anipose_t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],ani_gltf.nodes[ani_node].translation+[1]]).transpose()
                else:
                    anipose_t_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
                if ani_gltf.nodes[ani_node].rotation is not None:
                    anipose_r_mtx = Quaternion(ani_gltf.nodes[ani_node].rotation[3], ani_gltf.nodes[ani_node].rotation[0],\
                        ani_gltf.nodes[ani_node].rotation[1], ani_gltf.nodes[ani_node].rotation[2]).transformation_matrix
                else:
                    anipose_r_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
                if ani_gltf.nodes[ani_node].scale is not None:
                    anipose_s_mtx = numpy.array([[ani_gltf.nodes[ani_node].scale[0],0,0,0],\
                        [0,ani_gltf.nodes[ani_node].scale[1],0,0],[0,0,ani_gltf.nodes[ani_node].scale[2],0],[0,0,0,1]])
                else:
                    anipose_s_mtx = numpy.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
            # Overwrite model pose with animation pose per global variable preference
                if preserve_translation == False or (model_gltf.nodes[i].name in locators and always_transform_locators == True) \
                    or (model_gltf.nodes[i].name in always_transform_nodes):
                    t_mtx = anipose_t_mtx
                if preserve_rotation == False or (model_gltf.nodes[i].name in locators and always_transform_locators == True) \
                    or (model_gltf.nodes[i].name in always_transform_nodes):
                    r_mtx = anipose_r_mtx
                if preserve_scale == False or (model_gltf.nodes[i].name in locators and always_transform_locators == True) \
                    or (model_gltf.nodes[i].name in always_transform_nodes):
                    s_mtx = anipose_s_mtx
            #Delete current model (bind) pose
            for key in ['matrix', 'translation', 'rotation', 'scale']:
                if getattr(model_gltf.nodes[i], key) is not None:
                    setattr(model_gltf.nodes[i], key, None)
            #Insert new pose (T x R x S)
            model_gltf.nodes[i].matrix = numpy.dot(numpy.dot(t_mtx, r_mtx), s_mtx).flatten('F').tolist()
    # Copy animations into model
    model_gltf.convert_buffers(BufferFormat.BINARYBLOB)
    binary_blob = model_gltf.binary_blob()
    blob_len = len(model_gltf.binary_blob())
    allowed_transforms = []
    if preserve_translation == False:
        allowed_transforms.append('translation')
    if preserve_rotation == False:
        allowed_transforms.append('rotation')
    if preserve_scale == False:
        allowed_transforms.append('scale')
    if remove_model_ani == True:
        model_gltf.animations = [] # Remove any prior animations (binary data will be orphaned)
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
            if target_node_name in [x.name for x in model_gltf.nodes] \
                and (target_path in allowed_transforms or (target_node_name in locators and always_transform_locators == True) \
                or (target_node_name in always_transform_nodes)):
                transformed_model = True
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
    if transformed_model:
        return(model_gltf)
    else:
        return(ani_gltf)

def process_animation (animation_filename, model_filename = '', remove_model_ani = True):
    print("Processing {0}...".format(animation_filename))
    if os.path.exists(animation_filename+'.gltf'):
        ani_filename = animation_filename+'.gltf'
        output = 'GLTF'
    elif os.path.exists(animation_filename+'.glb'):
        ani_filename = animation_filename+'.glb'
        output = 'GLB'
    else:
        print("glTF file for {} not found, skipping...".format(animation_filename))
        return False
    ani_gltf = GLTF2().load(ani_filename)
    if ani_gltf.animations is None or len(ani_gltf.animations) < 1:
        print("Animation {} not found, skipping...".format(animation_filename))
        return False
    try:
        animation_metadata = read_struct_from_json(animation_filename+'.metadata')
    except:
        print("{0} missing or unreadable, no locators available.".format(animation_filename+'.metadata'))
        animation_metadata = { 'locators': [] }
    if model_filename == '' and len(ani_filename.split('_')) > 1:
        model_filename = ani_filename.split('_')[0]
    if os.path.exists(model_filename+'.glb'):
        model_gltf = GLTF2.load(model_filename+'.glb')
    elif os.path.exists(model_filename+'.gltf'):
        model_gltf = GLTF2.load(model_filename+'.gltf')
    elif len(models := glob.glob('*_c*.gl*')) > 0:
        model_gltf = GLTF2.load(models[0])
    else:
        print("Model {0}.glb/.gltf not found, skipping animation {1}...".format(model_filename, animation_filename))
        return False
    new_model = apply_animations_to_model_gltf (model_gltf, ani_gltf, \
        animation_metadata['locators'], remove_model_ani = remove_model_ani)
    new_model.convert_buffers(BufferFormat.BINARYBLOB)
    if output == 'GLB':
        new_model.save_binary("{}.glb".format(animation_filename))
        return True
    else:
        new_model.save("{}.gltf".format(animation_filename))
        return True

if __name__ == '__main__':
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to import into file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-k', '--keep_model_ani', help="Append animation onto model's animations if found", action="store_false")
        parser.add_argument('model_filename', help="Name of glTF file obtain model from (required).")
        parser.add_argument('animation_filename', help="Name of glTF file to import model into (required).")
        args = parser.parse_args()
        if os.path.exists(args.model_filename) and os.path.exists(args.animation_filename):
            process_animation(args.animation_filename.split('.gl')[0], args.model_filename.split('.gl')[0], remove_model_ani = args.keep_model_ani)
    else:
        animations = [x.split('.gl')[0] for x in glob.glob("*_m*.gl*") if len(x.split('_')) > 1]
        for animation_filename in animations:
            process_animation(animation_filename)
