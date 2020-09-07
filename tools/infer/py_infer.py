# Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import utils
import argparse
import numpy as np

import paddle.fluid as fluid


def parse_args():
    def str2bool(v):
        return v.lower() in ("true", "t", "1")

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--image_file", type=str)
    parser.add_argument("-d", "--model_dir", type=str)
    parser.add_argument("--use_gpu", type=str2bool, default=True)

    return parser.parse_args()


def create_predictor(args):
    if args.use_gpu:
        place = fluid.CUDAPlace(0)
    else:
        place = fluid.CPUPlace()

    exe = fluid.Executor(place)
    [program, feed_names, fetch_lists] = fluid.io.load_inference_model(
        args.model_dir, exe, model_filename="model", params_filename="params")
    compiled_program = fluid.compiler.CompiledProgram(program)

    return exe, compiled_program, feed_names, fetch_lists


def create_operators():
    size = 224
    img_mean = [0.485, 0.456, 0.406]
    img_std = [0.229, 0.224, 0.225]
    img_scale = 1.0 / 255.0

    decode_op = utils.DecodeImage()
    resize_op = utils.ResizeImage(resize_short=256)
    crop_op = utils.CropImage(size=(size, size))
    normalize_op = utils.NormalizeImage(
        scale=img_scale, mean=img_mean, std=img_std)
    totensor_op = utils.ToTensor()

    return [decode_op, resize_op, crop_op, normalize_op, totensor_op]


def preprocess(fname, ops):
    data = open(fname, 'rb').read()
    for op in ops:
        data = op(data)
    return data


def postprocess(outputs, topk=5):
    output = outputs[0]
    prob = np.array(output).flatten()
    index = prob.argsort(axis=0)[-topk:][::-1].astype('int32')
    return zip(index, prob[index])


def get_image_list(img_file):
    imgs_lists = []
    if img_file is None or not os.path.exists(img_file):
        raise Exception("not found any img file in {}".format(img_file))

    img_end = ['jpg', 'png', 'jpeg', 'JPEG', 'JPG', 'bmp']
    if os.path.isfile(img_file) and img_file.split('.')[-1] in img_end:
        imgs_lists.append(img_file)
    elif os.path.isdir(img_file):
        for single_file in os.listdir(img_file):
            if single_file.split('.')[-1] in img_end:
                imgs_lists.append(os.path.join(img_file, single_file))
    if len(imgs_lists) == 0:
        raise Exception("not found any img file in {}".format(img_file))
    return imgs_lists


def main():
    args = parse_args()
    operators = create_operators()
    exe, program, feed_names, fetch_lists = create_predictor(args)

    image_list = get_image_list(args.image_file)
    for idx, filename in enumerate(image_list):
        data = preprocess(filename, operators)
        data = np.expand_dims(data, axis=0)
        outputs = exe.run(program,
                          feed={feed_names[0]: data},
                          fetch_list=fetch_lists,
                          return_numpy=False)
        probs = postprocess(outputs)
        print("Current image file: {}".format(filename))
        for idx, prob in probs:
            print("\tclass id: {:d}, probability: {:.4f}".format(idx, prob))


if __name__ == "__main__":
    main()
