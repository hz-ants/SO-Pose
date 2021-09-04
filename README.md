# SO-Pose
This repository contains codes of ICCV2021 paper: SO-Pose: Exploiting Self-Occlusion for Direct 6D Pose Estimation
This paper is basically an incremental work to paper: GDR-Net: Geometry-Guided Direct Regression Network for Monocular 6D Object Pose Estimation.
We analyze and leverage self-occlusion in 6D pose estimation.

Datasets
----------
The code is based on the released code of GDR-Net in this [git](https://github.com/THU-DA-6D-Pose-Group/GDR-Net.git) (The code of GDR-Net is already included)
The struture of the datasets is the same.

Since we need ground truth 2D-3D matching and self-occlusion results, we provide generation methods in .gdrn_selfocc_modeling/tools.
Please refer to generate_*.py.
Note that public renderers (e.g. EGL, GLUMPY) may introduce noise in rendering, the inherent relations between P (2D-3D matching) and Q (self-occlusion) are not guaranteed. So if you use a renderer for efficiency, please make sure that P and Q lie on the same line.

Training and Testing
----------------
Please directly run ./gdrn_selfocc_modeling/main_gdrn.py for training and testing.

Import parameters include
>> config-file : the path to the configuration file.

>> resume: whether to continue the training process from the last checkpoint.

>> eval-only: whether to directly evalute the model.

Trained Models
--------------
The trained models can be downloaded [here](https://drive.google.com/file/d/136ExcMykxsVVSzOiGQVYspq1fx9Hjd6R/view?usp=sharing).
PLease unzip the trained models in the directory specified in the configuration file.

If you find the code useful, please cite the following papers:

>>[1]Wang, G., Manhardt, F., Tombari, F., & Ji, X. (2021). GDR-Net: Geometry-Guided Direct Regression Network for Monocular 6D Object Pose Estimation. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (pp. 16611-16621).

>>[2]Di, Y., Manhardt, F., Wang, G., Ji, X., Navab, N., & Tombari, F. (2021). SO-Pose: Exploiting Self-Occlusion for Direct 6D Pose Estimation. arXiv preprint arXiv:2108.08367.


