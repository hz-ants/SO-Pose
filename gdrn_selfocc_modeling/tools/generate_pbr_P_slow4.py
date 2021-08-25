# 产生Q0坐标，同时计算occlusion mask

import sys

sys.path.append('../')
import numpy as np
from PIL import Image, ImageFile
import os
import matplotlib.image as mp
from plyfile import PlyData
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import ref
from _collections import OrderedDict
import os.path as osp
import mmcv

LM_13_OBJECTS = [
    "ape",
    "benchvise",
    "camera",
    "can",
    "cat",
    "driller",
    "duck",
    "eggbox",
    "glue",
    "holepuncher",
    "iron",
    "lamp",
    "phone",
]  # no bowl, cup
LM_OCC_OBJECTS = ["ape", "can", "cat", "driller", "duck", "eggbox", "glue", "holepuncher"]

intrinsic_matrix = {
    'linemod': np.array([[572.4114, 0., 325.2611],
                         [0., 573.57043, 242.04899],
                         [0., 0., 1.]]),
}


def transformer(P0, R, t):  # P0, n,3
    P = (np.matmul(R, P0.T)).T + t.reshape(1, 3)
    return P


def transformer_back(P, R, t):  # 计算P0=RTP-RTt  P, 3*1
    P0 = np.matmul(R.T, P) - np.matmul(R.T, t)
    return P0

# P0 n,3
def projector(P0, K, R, t):  # 计算相机投影， 将P0经过R， t变换再投影到图像上
    p = (np.matmul(K, P0.T)).T / P0[:, 2:]  # n,3
    p = p[:, 0:2] / p[:, 2:]
    return p


def pointintriangle(A, B, C, P):  # 判断一点是否在3角面片内部，ABC是三角面片3个点
    # P :2*1  A,B,C : n,2
    v0 = C - A  # n,2
    v1 = B - A
    v2 = P.T - A

    dot00 = np.sum(v0 * v0, axis=1)  # n,1
    dot01 = np.sum(v0 * v1, axis=1)
    dot02 = np.sum(v0 * v2, axis=1)
    dot11 = np.sum(v1 * v1, axis=1)
    dot12 = np.sum(v1 * v2, axis=1)

    down = dot00 * dot11 - dot01 * dot01  # n,1
    down_save = down.copy()
    down[down < 1e-7] = 1
    inverdeno = 1 / down
    u = (dot11 * dot02 - dot01 * dot12) * inverdeno  # n,1
    v = (dot00 * dot12 - dot01 * dot02) * inverdeno
    mask = (down_save > 1e-6) & (u >= 0) & (v >= 0) & (u+v <= 1)
    return mask


def modelload(model_dir, ids, scale=1000.):
    modellist = {}
    for obj in ids:
        print("loading model", f"{obj:06d}")
        model_path = osp.join(model_dir, "obj_{:06d}.ply".format(obj))
        ply = PlyData.read(model_path)
        vert = np.asarray(
            [ply['vertex'].data['x'] / scale, ply['vertex'].data['y'] / scale,
             ply['vertex'].data['z'] / scale]).transpose()
        norm_d = np.asarray(
            [ply['vertex'].data['nx'], ply['vertex'].data['ny'], ply['vertex'].data['nz']]).transpose()
        vert_id = [id for id in ply['face'].data['vertex_indices']]
        vert_id = np.asarray(vert_id, np.int64)
        modellist[str(obj)] = {
            "vert": vert,
            "norm_d": norm_d,
            "vert_id": vert_id,
        }
    return modellist


class estimate_coor_P0():
    def __init__(self, rootdir, modeldir, start_id, end_id):  # /data/wanggu//Storage/BOP_DATASETS/lm/train_pbr
        self.dataset_root = rootdir
        self.modeldir = modeldir
        self.start_id = start_id
        self.end_id = end_id
        # NOTE: careful! Only the selected objects
        self.objs = LM_OCC_OBJECTS
        self.cat_ids = [cat_id for cat_id, obj_name in ref.lm_full.id2obj.items() if obj_name in self.objs]
        # map selected objs to [0, num_objs-1]
        self.cat2label = {v: i for i, v in enumerate(self.cat_ids)}  # id_map
        self.label2cat = {label: cat for cat, label in self.cat2label.items()}
        self.obj2label = OrderedDict((obj, obj_id) for obj_id, obj in enumerate(self.objs))
        self.scenes = [f"{i:06d}" for i in range(self.start_id, self.end_id)]
        self.xyz_root = osp.join(self.dataset_root, "xyz_crop")
        self.model = modelload(modeldir, self.cat_ids)
        self.new_xyz_root = osp.join(self.dataset_root, "xyz_crop_lm")

    def run(self, scale=1000):
        camK = intrinsic_matrix["linemod"].astype(np.float32)
        camK_inv = np.linalg.inv(camK)
        height = 480
        width = 640
        for scene in self.scenes:
            scene_id = int(scene)
            scene_root = osp.join(self.dataset_root, scene)
            gt_dict = mmcv.load(osp.join(scene_root, "scene_gt.json"))
            # gt_info_dict = mmcv.load(osp.join(scene_root, "scene_gt_info.json"))
            # cam_dict = mmcv.load(osp.join(scene_root, "scene_camera.json"))
            basic_out_path = osp.join(self.new_xyz_root, f"{scene_id:06d}")
            if not os.path.exists(basic_out_path):
                os.makedirs(basic_out_path)
            for str_im_id in gt_dict.keys():
                int_im_id = int(str_im_id)
                print("processing seq:{:06d} img:{:06d}".format(scene_id, int_im_id))
                rgb_path = osp.join(scene_root, "rgb/{:06d}.jpg").format(int_im_id)
                assert osp.exists(rgb_path), rgb_path

                '''
                show image
                rgb = mmcv.imread(rgb_path, "unchanged")
                plt.imshow(rgb)
                plt.show()
                '''

                for anno_i, anno in enumerate(gt_dict[str_im_id]):
                    obj_id = anno["obj_id"]

                    if obj_id in self.cat_ids:
                        out_path = osp.join(self.new_xyz_root, f"{scene_id:06d}/{int_im_id:06d}_{anno_i:06d}-xyz.pkl")
                        if osp.exists(out_path):
                            continue
                        R = np.array(anno["cam_R_m2c"], dtype="float32").reshape(3, 3)
                        t = (np.array(anno["cam_t_m2c"], dtype="float32") / 1000.0).reshape(3, 1)
                        # mask_file = osp.join(scene_root, "mask/{:06d}_{:06d}.png".format(int_im_id, anno_i))
                        mask_visib_file = osp.join(scene_root, "mask/{:06d}_{:06d}.png".format(int_im_id, anno_i))
                        # assert osp.exists(mask_file), mask_file
                        assert osp.exists(mask_visib_file), mask_visib_file
                        # load mask visib  TODO: load both mask_visib and mask_full
                        mask = mmcv.imread(mask_visib_file, "unchanged")
                        mask = mask.astype(np.bool).astype(np.float)
                        if mask.sum() == 0:
                            P = {
                                "xyz_crop": np.zeros((height, width, 3), dtype=np.float16),
                                "xyxy": [0, 0, width - 1, height - 1],
                            }

                        else:

                            xyz_path = osp.join(self.xyz_root, f"{scene_id:06d}/{int_im_id:06d}_{anno_i:06d}-xyz.pkl")
                            assert osp.exists(xyz_path), xyz_path
                            xyz = mmcv.load(xyz_path)
                            # begin to estimate new xyz

                            pixellist = np.zeros([height, width]) + 100  # 加一个大数
                            # 实际上就是将每个3角面片投影回来，查看其中包含的整点像素，为其提供一个估计，然后最后选择能看到的那个，Z值最小
                            vert = self.model[str(obj_id)]["vert"]
                            norm_d = self.model[str(obj_id)]["norm_d"]
                            vert_id = self.model[str(obj_id)]["vert_id"]
                            # project all vertices
                            vert_trans = transformer(vert, R, t)
                            d_trans = (np.matmul(R, (norm_d[vert_id[:, 0], :]).T)).T
                            vert_proj = projector(vert_trans, camK, R, t)  # n, 2
                            # construct triangle
                            A_before = vert_trans[vert_id[:, 0], :]
                            A = vert_proj[vert_id[:, 0], :]
                            B = vert_proj[vert_id[:, 1], :]
                            C = vert_proj[vert_id[:, 2], :]

                            # 生成P0的图， 之前只存储了Zp， 现在计算值
                            # pixellist is the result
                            P0_output = np.zeros([height, width, 3], dtype=np.float32)
                            x1, y1, x2, y2 = xyz["xyxy"]
                            for i in range(y1, y2+1):
                                for j in range(x1, x2+1):
                                    if mask[i][j] < 1:
                                        continue
                                    else:
                                        point = np.array([j, i, 1])
                                        point = point.reshape(3, 1)  #3,1
                                        flag = pointintriangle(A, B, C, point[0:2, :])
                                        if flag.sum() == 0:
                                            continue
                                        '''for test'''
                                        '''
                                        ids = np.arange(0, vert_id.shape[0])
                                        selected = ids[flag]
                                        s_a = A[selected, :]
                                        s_b =B[selected, :]
                                        s_c = C[selected,:]
                                        flag = pointintriangle(s_a, s_b, s_c, point[0:2, :])
                                        '''
                                        ''''''
                                        p_A = A_before[flag, :]
                                        p_d = d_trans[flag, :]
                                        plane_d = np.sum(p_d * p_A, axis=1).reshape(-1, 1)  # m, 1
                                        point_diretion = np.matmul(camK_inv, point)   # 3, 1
                                        down_Z = np.matmul(p_d, point_diretion)  # m, 1
                                        Z_p = plane_d / down_Z
                                        Z_p = np.abs(Z_p)
                                        Z_p_final = np.min(Z_p)
                                        P = (Z_p_final * point_diretion)
                                        P0 = transformer_back(P, R, t)
                                        # P0_3 = P0.reshape(3)
                                        P0_output[i, j, :] = P0.reshape(3)  # 边界上的点在计算的时候会出现错误， 没有完全包裹住

                            # xyz_value = xyz["xyz_crop"]
                            P = {
                                "xyz_crop": P0_output[y1:y2 + 1, x1:x2 + 1, :],
                                "xyxy": [x1, y1, x2, y2],
                            }

                        #outpath = osp.join(self.new_xyz_root, f"{scene_id:06d}/{int_im_id:06d}_{anno_i:06d}-xyz.pkl")
                        mmcv.dump(P, out_path)


if __name__ == "__main__":
    model_dir = "/data/wanggu/Storage/BOP_DATASETS/lmo/models"
    root_dir = "/data/wanggu/Storage/BOP_DATASETS/lm/train_pbr"
    G_P = estimate_coor_P0(root_dir, model_dir, 47, 50)
    G_P.run()
