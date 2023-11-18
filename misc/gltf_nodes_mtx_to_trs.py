# GitHub eArmada8/kuro_mdl_tool

try:
    import numpy, shutil, sys, os, glob
    from pyquaternion import Quaternion
    from pygltflib import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise   

def convert_gltf_nodes_matrix_to_trs (model_gltf):
    for i in range(len(model_gltf.nodes)):
        # Model (bind) pose
        if model_gltf.nodes[i].matrix is not None:
            model_t = model_gltf.nodes[i].matrix[12:15]
            model_s = [numpy.linalg.norm(model_gltf.nodes[i].matrix[0:3]), numpy.linalg.norm(model_gltf.nodes[i].matrix[4:7]),\
                numpy.linalg.norm(model_gltf.nodes[i].matrix[8:11])]
            r_mtx = numpy.array([(model_gltf.nodes[i].matrix[0:3]/model_s[0]).tolist(),\
                (model_gltf.nodes[i].matrix[4:7]/model_s[1]).tolist(),\
                (model_gltf.nodes[i].matrix[8:11]/model_s[2]).tolist()]) # Row-major
            # Enforce orthogonality of rotation matrix, Premelani W and Bizard P "Direction Cosine Matrix IMU: Theory" Diy Drone: Usa 1 (2009).
            if (error := numpy.dot(r_mtx[0],r_mtx[1])) != 0.0:
                vectors = [r_mtx[0]-(error/2)*r_mtx[1], r_mtx[1]-(error/2)*r_mtx[0]]
                vectors.append(numpy.cross(vectors[0], vectors[1]))
                r_mtx = numpy.array([x/numpy.linalg.norm(x) for x in vectors]).transpose() # Column-major
            else:
                r_mtx = r_mtx.transpose() # Column-major
            model_q = list(Quaternion(matrix = r_mtx)) #wxyz
            model_r = model_q[1:] + [model_q[0]] #xyzw
        else:
            if model_gltf.nodes[i].translation is not None:
                model_t = model_gltf.nodes[i].translation
            else:
                model_t = [0.0,0.0,0.0]
            if model_gltf.nodes[i].rotation is not None:
                model_r = model_gltf.nodes[i].rotation
            else:
                model_r = [0.0,0.0,0.0,1.0]
            if model_gltf.nodes[i].scale is not None:
                model_s = model_gltf.nodes[i].scale
            else:
                model_s = [1.0,1.0,1.0]
        #Delete current model (bind) pose
        for key in ['matrix', 'translation', 'rotation', 'scale']:
            if getattr(model_gltf.nodes[i], key) is not None:
                setattr(model_gltf.nodes[i], key, None)
        #Insert new pose (T x R x S)
        if model_t != [0.0,0.0,0.0]:
            model_gltf.nodes[i].translation = model_t
        if model_r != [0.0,0.0,0.0,1.0]:
            model_gltf.nodes[i].rotation = model_r
        if model_s != [1.0,1.0,1.0]:
            model_gltf.nodes[i].scale = model_s
    return(model_gltf)

def process_gltf (gltf_filename):
    print("Processing {0}...".format(gltf_filename))
    try:
        model_gltf = GLTF2().load(gltf_filename)
    except:
        print("File {} not found, or is invalid, skipping...".format(gltf_filename))
        return False
    model_gltf = convert_gltf_nodes_matrix_to_trs (model_gltf)
    # Instead of overwriting backups, it will just tag a number onto the end
    backup_suffix = ''
    if os.path.exists(gltf_filename + '.bak' + backup_suffix):
        backup_suffix = '1'
        if os.path.exists(gltf_filename + '.bak' + backup_suffix):
            while os.path.exists(gltf_filename + '.bak' + backup_suffix):
                backup_suffix = str(int(backup_suffix) + 1)
        shutil.copy2(gltf_filename, gltf_filename + '.bak' + backup_suffix)
    else:
        shutil.copy2(gltf_filename, gltf_filename + '.bak')
    model_gltf.save(gltf_filename)
    return True

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
    gltf_files = glob.glob('*.glb')+glob.glob('*.gltf')
    for i in range(len(gltf_files)):
        process_gltf(gltf_files[i])