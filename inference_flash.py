import argparse
import datetime
import random
import time
from pathlib import Path
from tqdm import tqdm

import torch
import torchvision.transforms as standard_transforms
from torchvision.utils import save_image
import numpy as np

from PIL import Image
import cv2
from crowd_datasets import build_dataset
from engine import *
from models import build_model
import os
import warnings
import requests
from os.path import exists
from models.vgg_ import model_paths, model_urls

warnings.filterwarnings('ignore')


def get_args_parser():
    parser = argparse.ArgumentParser('Set parameters for P2PNet evaluation', add_help=False)

    # * Backbone
    parser.add_argument('--backbone', default='vgg16_bn', type=str,
                        help="name of the convolutional backbone to use")

    parser.add_argument('--input_video', default='../Video-tests/test1.mp4', type=str,
                        help="address of input video file")

    parser.add_argument('--row', default=2, type=int,
                        help="row number of anchor points")
    parser.add_argument('--line', default=2, type=int,
                        help="line number of anchor points")

    parser.add_argument('--output_dir', default='./logs/',
                        help='path where to save')
    parser.add_argument('--weight_path', default='./SHTechA.pth',
                        help='path where the trained weights saved')

    parser.add_argument('--gpu_id', default=0, type=int, help='the gpu used for evaluation')

    return parser


def load_model():
    # check if vgg backbone is available
    #if (not exists(model_paths['vgg16_bn'])):
     #   print('Downloading VGG!')
      #  url = model_urls['vgg16_bn']
       # r = requests.get(url, allow_redirects=True)
        #with open(model_paths['vgg16_bn'], 'wb') as f:
         #   f.write(r.content)
        #print('Finished Downloading')
    parser = argparse.ArgumentParser('P2PNet evaluation script', parents=[get_args_parser()])
    args = parser.parse_args()
    # os.environ["CUDA_VISIBLE_DEVICES"] = '{}'.format(args.gpu_id)

    # print(args)
    device = torch.device('cpu')
    # get the P2PNet
    model = build_model(args)
    # move to GPU
    model.to(device)
    # load trained model
    if args.weight_path is not None:
        checkpoint = torch.load(args.weight_path, map_location='cpu')
        model.load_state_dict(checkpoint['model'])
    # convert to eval mode
    model.eval()
    # create the pre-processing transform
    transform = standard_transforms.Compose([
        standard_transforms.ToTensor(),
        standard_transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    return model, transform, device


def image_inference(model, transform, device, img_file, raw_img_input=False, return_img=False):
    if raw_img_input:
        img_raw = img_file
    else:
        # set your image path here
        img_path = img_file
        # load the images
        img_raw = Image.open(img_path).convert('RGB')
    # round the size
    width, height = img_raw.size
    new_width = width // 128 * 128
    new_height = height // 128 * 128
    img_raw = img_raw.resize((new_width, new_height), Image.ANTIALIAS)
    # pre-proccessing
    img_raw.save('resized.jpg')
    img = transform(img_raw)
    samples = torch.Tensor(img).unsqueeze(0)
    samples = samples.to(device)
    # run inference
    outputs = model(samples)
    outputs_scores = torch.nn.functional.softmax(outputs['pred_logits'], -1)[:, :, 1][0]

    outputs_points = outputs['pred_points'][0]

    threshold = 0.5
    # filter the predictions
    points = outputs_points[outputs_scores > threshold].detach().cpu().numpy().tolist()
    predict_cnt = int((outputs_scores > threshold).sum())

    outputs_scores = torch.nn.functional.softmax(outputs['pred_logits'], -1)[:, :, 1][0]

    outputs_points = outputs['pred_points'][0]
    print(len(points))
    # draw the predictions
    size = 2
    img_to_draw = cv2.cvtColor(np.array(img_raw), cv2.COLOR_RGB2BGR)
    for p in points:
        img_to_draw = cv2.circle(img_to_draw, (int(p[0]), int(p[1])), size, (0, 0, 255), -1)
    # save the visualized image
    if return_img:
        return img_to_draw, predict_cnt
    else:
        cv2.imwrite(img_file, img_to_draw)
        return predict_cnt


def video_reader(videoFile):
    cap = cv2.VideoCapture(videoFile)
    while (cap.isOpened()):
        ret, cv2_im = cap.read()
        print(1)
        if ret:
            converted = cv2.cvtColor(cv2_im, cv2.COLOR_BGR2RGB)
            pil_im = Image.fromarray(converted)
            yield pil_im

        elif not ret:
            break
    cap.release()


def video_inference(model, transform, device, video_file):
    result = []
    for frame in tqdm(video_reader(video_file)):
        print(frame)
        img_raw = frame
        # round the size
        width, height = img_raw.size
        new_width = width // 128 * 128
        new_height = height // 128 * 128
        img_raw = img_raw.resize((new_width, new_height), Image.ANTIALIAS)
        frames_size = (new_width, new_height)
        # pre-proccessing
        img = transform(img_raw)

        samples = torch.Tensor(img).unsqueeze(0)
        samples = samples.to(device)
        # run inference
        outputs = model(samples)
        outputs_scores = torch.nn.functional.softmax(outputs['pred_logits'], -1)[:, :, 1][0]

        outputs_points = outputs['pred_points'][0]

        threshold = 0.5
        # filter the predictions
        points = outputs_points[outputs_scores > threshold].detach().cpu().numpy().tolist()
        predict_cnt = int((outputs_scores > threshold).sum())
        print(predict_cnt)

        outputs_scores = torch.nn.functional.softmax(outputs['pred_logits'], -1)[:, :, 1][0]

        outputs_points = outputs['pred_points'][0]
        # draw the predictions
        size = 10
        img_to_draw = cv2.cvtColor(np.array(img_raw), cv2.COLOR_RGB2BGR)
        for p in points:
            img_to_draw = cv2.circle(img_to_draw, (int(p[0]), int(p[1])), size, (0, 0, 255), -1)
        # save the visualized image
        # cv2.imwrite(os.path.join(args.output_dir, 'pred{}.jpg'.format(predict_cnt)), img_to_draw)
        # break
        if result:
            result.write(img_to_draw)
            break
        else:
            result = cv2.VideoWriter(f'{video_file}.avi',
                                     cv2.VideoWriter_fourcc(*'MJPG'),
                                     10, frames_size)
            result.write(img_to_draw)
    result.release()
    return True
