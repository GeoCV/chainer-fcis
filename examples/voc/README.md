# Pascal VOC & SBD instance segmentation

![Example](../../static/voc_example.png)

## Inference

Trained model can be dowloaded [here](https://drive.google.com/open?id=1QDquG8SlbvnlsJpfMhuZn8g0tpe84lVt).

This model is converted from one trained by original repo.

```bash
# Pretrained model will be downloaded automatically
# or run below.
# python download_models.py

python demo.py
```

## Training

```bash
# Download dataset manually in ~/data/datasets/VOC
# or run below.
# python download_datasets.py --sbd

python train.py
```

## Evaluation

```bash
# Download dataset manually in ~/data/datasets/VOC
# or run below.
# python download_datasets.py --sbd

python evaluate.py
```

### Evaluation: Trained model by Our Repo

This is evaluation of model trained by our repo.

**FCIS ResNet101**

| Implementation | Sampling Strategy | mAP@0.5 | mAP@0.7 |
|:--------------:|:-----------------:|:-------:|:-------:|
| [Original](https://github.com/msracver/FCIS) | Random | 0.646 | 0.499 |
| Ours | Random | 0.628 | 0.486 |

***mAP@0.5***

| Implementation | aeroplane | bicycle | bird | boat | bottle | bus | car | cat | chair | cow | dining table | dog | horse | motorbike | person | potted plant | sheep | sofa | train | tv/monitor |
|:--------------:|:---------:|:-------:|:----:|:----:|:------:|:---:|:---:|:---:|:-----:|:---:|:------------:|:---:|:-----:|:---------:|:------:|:------------:|:-----:|:----:|:-----:|:----------:|
| [Original](https://github.com/msracver/FCIS) | 0.783 | 0.684 | 0.698 | 0.486 | 0.444 | 0.790 | 0.677 | 0.840 | 0.420 | 0.657 | 0.384 | 0.812 | 0.720 | 0.738 | 0.754 | 0.415 | 0.704 | 0.491 | 0.775 | 0.639 |
| Ours | 0.766 | 0.698 | 0.686 | 0.455 | 0.409 | 0.783 | 0.660 | 0.848 | 0.396 | 0.648 | 0.325 | 0.819 | 0.701 | 0.699 | 0.693 | 0.403 | 0.655 | 0.490 | 0.779 | 0.640 |

***mAP@0.7***

| Implementation | aeroplane | bicycle | bird | boat | bottle | bus | car | cat | chair | cow | dining table | dog | horse | motorbike | person | potted plant | sheep | sofa | train | tv/monitor |
|:--------------:|:---------:|:-------:|:----:|:----:|:------:|:---:|:---:|:---:|:-----:|:---:|:------------:|:---:|:-----:|:---------:|:------:|:------------:|:-----:|:----:|:-----:|:----------:|
| [Original](https://github.com/msracver/FCIS) | 0.649 | 0.455 | 0.570 | 0.338 | 0.333 | 0.754 | 0.547 | 0.745 | 0.246 | 0.534 | 0.245 | 0.703 | 0.478 | 0.530 | 0.543 | 0.264 | 0.533 | 0.324 | 0.660 | 0.536 |
| Ours | 0.616 | 0.425 | 0.586 | 0.329 | 0.306 | 0.726 | 0.527 | 0.751 | 0.228 | 0.479 | 0.163 | 0.705 | 0.526 | 0.547 | 0.477 | 0.255 | 0.501 | 0.363 | 0.659 | 0.543 |

### Evaluation: Converted model from Original Repo

This is evaluation of model trained by original repo and converted to chainer.

**FCIS ResNet101**

| Implementation | Sampling Strategy | mAP@0.5 | mAP@0.7 |
|:--------------:|:-----------------:|:-------:|:-------:|
| [Original](https://github.com/msracver/FCIS) | Random | 0.646 | 0.499 |
| Ours | Random | 0.615 | 0.480 |

***mAP@0.5***

| Implementation | aeroplane | bicycle | bird | boat | bottle | bus | car | cat | chair | cow | dining table | dog | horse | motorbike | person | potted plant | sheep | sofa | train | tv/monitor |
|:--------------:|:---------:|:-------:|:----:|:----:|:------:|:---:|:---:|:---:|:-----:|:---:|:------------:|:---:|:-----:|:---------:|:------:|:------------:|:-----:|:----:|:-----:|:----------:|
| [Original](https://github.com/msracver/FCIS) | 0.783 | 0.684 | 0.698 | 0.486 | 0.444 | 0.790 | 0.677 | 0.840 | 0.420 | 0.657 | 0.384 | 0.812 | 0.720 | 0.738 | 0.754 | 0.415 | 0.704 | 0.491 | 0.775 | 0.639 |
| Ours | 0.756 | 0.685 | 0.678 | 0.434 | 0.398 | 0.776 | 0.615 | 0.827 | 0.375 | 0.646 | 0.334 | 0.775 | 0.707 | 0.702 | 0.698 | 0.407 | 0.668 | 0.473 | 0.752 | 0.587 |

***mAP@0.7***

| Implementation | aeroplane | bicycle | bird | boat | bottle | bus | car | cat | chair | cow | dining table | dog | horse | motorbike | person | potted plant | sheep | sofa | train | tv/monitor |
|:--------------:|:---------:|:-------:|:----:|:----:|:------:|:---:|:---:|:---:|:-----:|:---:|:------------:|:---:|:-----:|:---------:|:------:|:------------:|:-----:|:----:|:-----:|:----------:|
| [Original](https://github.com/msracver/FCIS) | 0.649 | 0.455 | 0.570 | 0.338 | 0.333 | 0.754 | 0.547 | 0.745 | 0.246 | 0.534 | 0.245 | 0.703 | 0.478 | 0.530 | 0.543 | 0.264 | 0.533 | 0.324 | 0.660 | 0.536 |
| Ours | 0.629 | 0.475 | 0.568 | 0.307 | 0.309 | 0.717 | 0.512 | 0.746 | 0.231 | 0.517 | 0.200 | 0.685 | 0.486 | 0.518 | 0.491 | 0.252 | 0.511 | 0.327 | 0.626 | 0.500 |


## Dataset Download

- [Pascal VOC](http://host.robots.ox.ac.uk/pascal/VOC/)
- [SBD](http://home.bharathh.info/pubs/codes/SBD/download.html)

```bash
# Dataset will be downloaded to ~/data/datasets/VOC
python download_datasets.py --voc
python download_datasets.py --sbd
```
