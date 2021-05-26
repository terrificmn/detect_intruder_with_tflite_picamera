# python3
#
# Copyright 2019 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Example using TF Lite to detect objects with the Raspberry Pi camera."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import io
import re
import time
from datetime import datetime

from annotation import Annotator

import numpy as np
import picamera

from PIL import Image
from tflite_runtime.interpreter import Interpreter
import RPi.GPIO as GPIO

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
GPIO.setmode(GPIO.BCM)
GPIO.setup(4, GPIO.OUT)

def load_labels(path):
  """Loads the labels file. Supports files with or without index numbers."""
  with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    labels = {}
    for row_number, content in enumerate(lines):
      pair = re.split(r'[:\s]+', content.strip(), maxsplit=1)
      if len(pair) == 2 and pair[0].strip().isdigit():
        labels[int(pair[0])] = pair[1].strip()
      else:
        labels[row_number] = pair[0].strip()
  return labels


def set_input_tensor(interpreter, image):
  """Sets the input tensor."""
  tensor_index = interpreter.get_input_details()[0]['index']
  input_tensor = interpreter.tensor(tensor_index)()[0]
  input_tensor[:, :] = image


def get_output_tensor(interpreter, index):
  """Returns the output tensor at the given index."""
  output_details = interpreter.get_output_details()[index]
  tensor = np.squeeze(interpreter.get_tensor(output_details['index']))
  return tensor


def detect_objects(interpreter, image, threshold):
  """Returns a list of detection results, each a dictionary of object info."""
  set_input_tensor(interpreter, image)
  interpreter.invoke()

  # Get all output details
  boxes = get_output_tensor(interpreter, 0)
  classes = get_output_tensor(interpreter, 1)
  scores = get_output_tensor(interpreter, 2)
  count = int(get_output_tensor(interpreter, 3))

  results = []
  for i in range(count):
    if scores[i] >= threshold:
      result = {
          'bounding_box': boxes[i],
          'class_id': classes[i],
          'score': scores[i]
      }
      results.append(result)
  return results


def annotate_objects(annotator, results, labels):
  """Draws the bounding box and label for each object in the results."""
  for obj in results:
    # Convert the bounding box figures from relative coordinates
    # to absolute coordinates based on the original resolution
    ymin, xmin, ymax, xmax = obj['bounding_box']
    xmin = int(xmin * CAMERA_WIDTH)
    xmax = int(xmax * CAMERA_WIDTH)
    ymin = int(ymin * CAMERA_HEIGHT)
    ymax = int(ymax * CAMERA_HEIGHT)

    # Overlay the box, label, and score on the camera preview
    annotator.bounding_box([xmin, ymin, xmax, ymax])
    annotator.text([xmin, ymin],
                   '%s\n%.2f' % (labels[obj['class_id']], obj['score']))
    
    detected_class_id = labels[obj['class_id']]
    detected_score = obj['score']
    detected_size = (xmax-xmin)*(ymax-ymin)
    blink(detected_class_id, detected_score, detected_size)

      
#def blink(class_id, score, size):
#  if (class_id == 'person') & (score >= 0.6) & (size >=30000):
#    print(class_id, score, size)
#    GPIO.output(4, True)
#    
#  else:
#    GPIO.output(4, False)


def fileWrite() :
  """침입자가 있으면 기록하는 함수"""
  isHuman = 1 
  currentTime = datetime.now() #현재 시간
        
  #파일에 기록 #'a' 추가로 계속 기록
  with open('intruderList.txt', 'a') as reportFile :
    context = str(isHuman) + ' ' + str(currentTime.isoformat()) + '\n'
    reportFile.write(context) 


def obResultPrint(results):
  """ object detection이 끝나고 반환받은 결과로 사람이 60% 이상일 때만 기록하는 함수"""
  resultCnt = len(results)
  
  # 리스트 형태로 반환됨 리스값이 없다면 실행 안함
  if resultCnt != 0:
    for result in results:
      # 해당 결과 리스트에 딕셔너리로 되어 있음 - 비교 후 실행하며 라벨에 따라 class_id 0은 사람임
      if result['class_id'] == 0 and result['score'] >= 0.6 : # human 
        print('object has been detected - chance : {} %'.format(result['score'] * 100)) #단순히 출력용
        # 파일저장 함수 호출
        fileWrite()
          
      else :
        print('not detected. no intruder found')
  

def main():
  parser = argparse.ArgumentParser(
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument(
      '--model', help='File path of .tflite file.', default='data/detect.tflite')  #파라미터 고정
  parser.add_argument(
      '--labels', help='File path of labels file.', default='data/coco_labels.txt') #파라미터 고정
  parser.add_argument(
      '--threshold',
      help='Score threshold for detected objects.',
      required=False,
      type=float,
      default=0.5)
  
  args = parser.parse_args()
  
  labels = load_labels(args.labels)
  interpreter = Interpreter(args.model)
  interpreter.allocate_tensors()
  _, input_height, input_width, _ = interpreter.get_input_details()[0]['shape']

  with picamera.PiCamera(
      resolution=(CAMERA_WIDTH, CAMERA_HEIGHT), framerate=30) as camera:
    #방해되서 일단 주석처리
    #camera.start_preview()
    camera.start_preview(fullscreen=False, window=(800, 200, 640, 480))  #fullscreen모두 끔
    try:
      stream = io.BytesIO()
      annotator = Annotator(camera)
      for _ in camera.capture_continuous(
          stream, format='jpeg', use_video_port=True):
        stream.seek(0)
        image = Image.open(stream).convert('RGB').resize(
            (input_width, input_height), Image.ANTIALIAS)
        start_time = time.monotonic()
        results = detect_objects(interpreter, image, args.threshold)
        elapsed_ms = (time.monotonic() - start_time) * 1000
        
        #출력만 하는 함수
        obResultPrint(results)
        
        # 주석처리
        #annotator.clear()
        #annotate_objects(annotator, results, labels)
        #annotator.text([5, 0], '%.1fms' % (elapsed_ms))
        #annotator.update()

        stream.seek(0)
        stream.truncate()

    finally:
      camera.stop_preview()


if __name__ == '__main__':
  main()
