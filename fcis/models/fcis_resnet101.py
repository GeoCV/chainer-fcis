from __future__ import division

import chainer
import chainer.functions as F
import chainer.links as L
from chainercv.links.model.faster_rcnn.region_proposal_network import \
    RegionProposalNetwork
from chainercv.links.model.faster_rcnn.utils.loc2bbox import loc2bbox
import cupy
import fcis.functions
from fcis.models.resnet101 import ResNet101C1
from fcis.models.resnet101 import ResNet101C2
from fcis.models.resnet101 import ResNet101C3
from fcis.models.resnet101 import ResNet101C4
from fcis.models.resnet101 import ResNet101C5
import fcn
import numpy as np
import os.path as osp


class FCISResNet101(chainer.Chain):

    feat_stride = 16
    mean_bgr = np.array([103.06, 115.90, 123.15], dtype=np.float32)
    model_dir = osp.expanduser('~/data/models/chainer/')

    def __init__(
            self, n_class=81,
            ratios=[0.5, 1, 2],
            anchor_scales=[4, 8, 16, 32],
            n_train_pre_nms=6000, n_train_post_nms=300,
            n_test_pre_nms=6000, n_test_post_nms=300,
            nms_thresh=0.7, rpn_min_size=2,
            group_size=7, roi_size=21,
            loc_normalize_mean=(0.0, 0.0, 0.0, 0.0),
            loc_normalize_std=(0.2, 0.2, 0.5, 0.5),
    ):
        super(FCISResNet101, self).__init__()
        proposal_creator_params = {
            'nms_thresh': nms_thresh,
            'n_train_pre_nms': n_train_pre_nms,
            'n_train_post_nms': n_train_post_nms,
            'n_test_pre_nms': n_test_pre_nms,
            'n_test_post_nms': n_test_post_nms,
            'force_cpu_nms': False,
            'min_size': rpn_min_size,
        }

        self.n_class = n_class
        self.spatial_scale = 1. / self.feat_stride
        self.group_size = group_size
        self.roi_size = roi_size
        self.loc_normalize_mean = loc_normalize_mean
        self.loc_normalize_std = loc_normalize_std

        initialW = chainer.initializers.Normal(0.01)

        with self.init_scope():
            # ResNet
            self.res1 = ResNet101C1()
            self.res2 = ResNet101C2()
            self.res3 = ResNet101C3()
            self.res4 = ResNet101C4()
            self.res5 = ResNet101C5()

            # RPN
            self.rpn = RegionProposalNetwork(
                1024, 512,
                ratios=ratios,
                anchor_scales=anchor_scales,
                feat_stride=self.feat_stride,
                initialW=initialW,
                proposal_creator_params=proposal_creator_params
            )

            # PSROI Pooling
            self.psroi_conv1 = L.Convolution2D(
                2048, 1024, 1, 1, 0, initialW=initialW)
            self.psroi_conv2 = L.Convolution2D(
                1024, group_size*group_size*self.n_class*2, 1, 1, 0,
                initialW=initialW)
            self.psroi_conv3 = L.Convolution2D(
                1024, group_size*group_size*2*4, 1, 1, 0, initialW=initialW)

    def __call__(self, x, scale=1.0, iter2=True):
        img_size = x.shape[2:]

        # Feature Extractor
        h = self.res1(x)
        h = self.res2(h)
        h = self.res3(h)
        h = self.res4(h)

        # RPN
        rpn_locs, rpn_scores, rois, roi_indices, anchor = self.rpn(
            h, img_size, scale)
        roi_indices = roi_indices.astype(np.float32)
        indices_and_rois = self.xp.concatenate(
            (roi_indices[:, None], rois), axis=1)

        # ResNet101C5 with dilated convolution
        h = self.res5(h)

        # Convolution for PSROI pooling
        h = F.relu(self.psroi_conv1(h))
        h_cls_seg = self.psroi_conv2(h)
        h_locs = self.psroi_conv3(h)

        # PSROI pooling and regression
        roi_seg_scores, roi_cls_locs, roi_cls_scores = self._pool_and_predict(
            indices_and_rois, h_cls_seg, h_locs)
        roi_cls_probs = F.softmax(roi_cls_scores)
        roi_seg_probs = F.softmax(roi_seg_scores)
        roi_seg_probs = roi_seg_probs.array
        roi_cls_probs = roi_cls_probs.array

        if iter2:
            # 2nd Iteration
            # get rois2 for more precise prediction
            roi_cls_locs = roi_cls_locs.array
            roi_locs = roi_cls_locs[:, 1, :]
            mean = self.xp.array(self.loc_normalize_mean, np.float32)
            std = self.xp.array(self.loc_normalize_std, np.float32)
            roi_locs = roi_locs * std + mean
            rois2 = loc2bbox(rois, roi_locs)
            H, W = img_size
            rois2[:, 0::2] = self.xp.clip(rois2[:, 0::2], 0, H)
            rois2[:, 1::2] = self.xp.clip(rois2[:, 1::2], 0, W)

            # PSROI pooling and regression
            indices_and_rois2 = self.xp.concatenate(
                (roi_indices[:, None], rois2), axis=1)
            roi_seg_scores2, _, roi_cls_scores2 = self._pool_and_predict(
                indices_and_rois2, h_cls_seg, h_locs)
            roi_cls_probs2 = F.softmax(roi_cls_scores2)
            roi_seg_probs2 = F.softmax(roi_seg_scores2)
            roi_seg_probs2 = roi_seg_probs2.array
            roi_cls_probs2 = roi_cls_probs2.array

            # concat 1st and 2nd iteration results
            rois = self.xp.concatenate((rois, rois2))
            roi_indices = self.xp.concatenate((roi_indices, roi_indices))
            roi_cls_probs = self.xp.concatenate(
                (roi_cls_probs, roi_cls_probs2))
            roi_seg_probs = self.xp.concatenate(
                (roi_seg_probs, roi_seg_probs2))

        return roi_indices, rois, roi_seg_probs, roi_cls_probs

    def _pool_and_predict(
            self, indices_and_rois, h_cls_seg, h_locs, gt_roi_labels=None):
        # PSROI Pooling
        # shape: (n_rois, n_class*2, roi_size, roi_size)
        pool_cls_seg = _psroi_pooling_2d_yx(
            h_cls_seg, indices_and_rois, self.roi_size, self.roi_size,
            self.spatial_scale, group_size=self.group_size,
            output_dim=self.n_class*2)
        # shape: (n_rois, n_class, 2, roi_size, roi_size)
        pool_cls_seg = pool_cls_seg.reshape(
            (-1, self.n_class, 2, self.roi_size, self.roi_size))
        # shape: (n_rois, 2*4, roi_size, roi_size)
        pool_locs = _psroi_pooling_2d_yx(
            h_locs, indices_and_rois, self.roi_size, self.roi_size,
            self.spatial_scale, group_size=self.group_size,
            output_dim=2*4)

        # Classfication
        # Group Max
        # shape: (n_rois, n_class, roi_size, roi_size)
        h_cls = pool_cls_seg.transpose((0, 1, 3, 4, 2))
        h_cls = F.max(h_cls, axis=4)

        # Global pooling (vote)
        # shape: (n_rois, n_class)
        roi_cls_scores = _global_average_pooling_2d(h_cls)

        # Bbox Regression
        # shape: (n_rois, 2*4)
        roi_cls_locs = _global_average_pooling_2d(pool_locs)
        n_rois = roi_cls_locs.shape[0]
        roi_cls_locs = roi_cls_locs.reshape((n_rois, 2, 4))

        # Mask Regression
        # shape: (n_rois, n_class, 2, roi_size, roi_size)
        # Group Pick by Score
        if gt_roi_labels is None:
            max_cls_idx = roi_cls_scores.array.argmax(axis=1)
        else:
            max_cls_idx = gt_roi_labels
        # shape: (n_rois, 2, roi_size, roi_size)
        roi_seg_scores = pool_cls_seg[np.arange(len(max_cls_idx)), max_cls_idx]

        return roi_seg_scores, roi_cls_locs, roi_cls_scores

    def prepare(self, orig_img, target_height=600, max_width=1000):
        img = orig_img.copy()
        img = img.transpose((1, 2, 0))  # C, H, W -> H, W, C
        img = fcis.utils.resize_image(img, target_height, max_width)
        img = img.astype(np.float32)
        img -= self.mean_bgr
        img = img.transpose((2, 0, 1))  # H, W, C -> C, H, W
        return img

    def predict(
            self, orig_imgs,
            target_height=600, max_width=1000,
            score_thresh=0.7, nms_thresh=0.3,
            mask_merge_thresh=0.5, binary_thresh=0.4,
            min_drop_size=2,
            iter2=True, mask_voting=True):

        bboxes = []
        whole_masks = []
        labels = []
        cls_probs = []

        for orig_img in orig_imgs:
            _, orig_H, orig_W = orig_img.shape
            img = self.prepare(
                orig_img, target_height, max_width)
            img = img.astype(np.float32)
            scale = img.shape[1] / orig_H
            with chainer.using_config('train', False), \
                    chainer.function.no_backprop_mode():
                # inference
                x = chainer.Variable(self.xp.array(img[None]))
                _, bbox, seg_prob, cls_prob = self.__call__(
                    x, scale, iter2=iter2)

            # assume that batch_size = 1
            bbox = bbox / scale

            # shape: (n_rois, H, W)
            mask_prob = seg_prob[:, 1, :, :]

            # shape: (n_rois, 4)
            bbox[:, 0::2] = cupy.clip(bbox[:, 0::2], 0, orig_H)
            bbox[:, 1::2] = cupy.clip(bbox[:, 1::2], 0, orig_W)

            # voting
            # cpu voting is only implemented
            bbox = chainer.cuda.to_cpu(bbox)
            cls_prob = chainer.cuda.to_cpu(cls_prob)
            mask_prob = chainer.cuda.to_cpu(mask_prob)

            if mask_voting:
                bbox, mask_prob, label, cls_prob = fcis.mask.mask_voting(
                    bbox, mask_prob, cls_prob, self.n_class,
                    orig_H, orig_W, score_thresh, nms_thresh,
                    mask_merge_thresh, binary_thresh)
            else:
                label = cls_prob.argmax(axis=1)
                label_mask = label != 0
                cls_prob = cls_prob[np.arange(len(cls_prob)), label]
                keep_indices = cls_prob > score_thresh
                keep_indices = np.logical_and(
                    label_mask, keep_indices)
                bbox = bbox[keep_indices]
                mask_prob = mask_prob[keep_indices]
                cls_prob = cls_prob[keep_indices]
                label = label[keep_indices]

            height = bbox[:, 2] - bbox[:, 0]
            width = bbox[:, 3] - bbox[:, 1]
            keep_indices = np.where(
                (height > min_drop_size) & (width > min_drop_size))[0]
            bbox = bbox[keep_indices]
            mask_prob = mask_prob[keep_indices]
            cls_prob = cls_prob[keep_indices]
            label = label[keep_indices]

            mask = fcis.utils.mask_probs2mask(mask_prob, bbox, binary_thresh)
            whole_mask = fcis.utils.mask2whole_mask(
                mask, bbox, (orig_H, orig_W))
            whole_masks.append(whole_mask)
            bboxes.append(bbox)
            labels.append(label)
            cls_probs.append(cls_prob)

        return bboxes, whole_masks, labels, cls_probs

    def download(self, dataset='coco'):
        if dataset == 'voc':
            url = 'https://drive.google.com/uc?id=1QDquG8SlbvnlsJpfMhuZn8g0tpe84lVt'  # NOQA
            path = osp.join(self.model_dir, 'fcis_voc.npz')
            md5 = '264ef0d2b620ad9cd4872afccf922a1b'
        else:
            url = 'https://drive.google.com/uc?id=0B5DV6gwLHtyJZTR0NFllNGlwS3M'
            path = osp.join(self.model_dir, 'fcis_coco.npz')
            md5 = '689f9f01e7ee37f591b218e49c6686fb'
        return fcn.data.cached_download(url=url, path=path, md5=md5)

    def init_weight(self, resnet101=None):
        if resnet101 is None:
            resnet101 = chainer.links.ResNet101Layers(pretrained_model='auto')

        n_layer_dict = {
            'res2': 3,
            'res3': 4,
            'res4': 23,
            'res5': 3
        }

        def copy_conv(conv, orig_conv):
            assert conv is not orig_conv
            assert conv.W.array.shape == orig_conv.W.array.shape
            conv.W.array[:] = orig_conv.W.array

        def copy_bn(bn, orig_bn):
            assert bn is not orig_bn
            assert bn.gamma.array.shape == orig_bn.gamma.array.shape
            assert bn.beta.array.shape == orig_bn.beta.array.shape
            assert bn.avg_var.shape == orig_bn.avg_var.shape
            assert bn.avg_mean.shape == orig_bn.avg_mean.shape
            bn.gamma.array[:] = orig_bn.gamma.array
            bn.beta.array[:] = orig_bn.beta.array
            bn.avg_var[:] = orig_bn.avg_var
            bn.avg_mean[:] = orig_bn.avg_mean

        def copy_bottleneck(bottle, orig_bottle, n_conv):
            for i in range(0, n_conv):
                conv_name = 'conv{}'.format(i + 1)
                conv = getattr(bottle, conv_name)
                orig_conv = getattr(orig_bottle, conv_name)
                copy_conv(conv, orig_conv)

                bn_name = 'bn{}'.format(i + 1)
                bn = getattr(bottle, bn_name)
                orig_bn = getattr(orig_bottle, bn_name)
                copy_bn(bn, orig_bn)

        def copy_block(block, orig_block, res_name):
            n_layer = n_layer_dict[res_name]
            bottle = getattr(block, '{}_a'.format(res_name))
            copy_bottleneck(bottle, orig_block.a, 4)
            for i in range(1, n_layer):
                bottle = getattr(block, '{0}_b{1}'.format(res_name, i))
                orig_bottle = getattr(orig_block, 'b{}'.format(i))
                copy_bottleneck(bottle, orig_bottle, 3)

        copy_conv(self.res1.conv1, resnet101.conv1)
        copy_bn(self.res1.bn1, resnet101.bn1)
        copy_block(self.res2, resnet101.res2, 'res2')
        copy_block(self.res3, resnet101.res3, 'res3')
        copy_block(self.res4, resnet101.res4, 'res4')
        copy_block(self.res5, resnet101.res5, 'res5')


def _psroi_pooling_2d_yx(
        x, indices_and_rois, outh, outw,
        spatial_scale, group_size, output_dim):
    xy_indices_and_rois = indices_and_rois[:, [0, 2, 1, 4, 3]]
    pool = fcis.functions.psroi_pooling_2d(
        x, xy_indices_and_rois, outh, outw, spatial_scale,
        group_size, output_dim)
    return pool


def _global_average_pooling_2d(x):
    n_rois, n_channel, H, W = x.array.shape
    h = F.average_pooling_2d(x, (H, W), stride=1)
    h = F.reshape(h, (n_rois, n_channel))
    return h
