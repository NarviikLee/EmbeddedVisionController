import tflite_runtime.interpreter as tflite
import numpy as np

interpreter = tflite.Interpreter(model_path='models/efficientdet_lite0.tflite')
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
print(input_details)