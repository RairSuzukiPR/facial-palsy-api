import base64
import os
import shutil

import cv2
import mediapipe as mp
from fastapi import UploadFile, File
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
import numpy as np
import matplotlib.pyplot as plt


class SessionService:
    def classify_image(self, file: UploadFile = File(...), facialExpression: str = File(...)):
        current_directory = os.getcwd()
        file_path = os.path.join(current_directory, "app/services/image.jpg")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        base_options = python.BaseOptions(model_asset_path='./face_landmarker_v2_with_blendshapes.task')
        options = vision.FaceLandmarkerOptions(base_options=base_options,
                                               output_face_blendshapes=True,
                                               output_facial_transformation_matrixes=True,
                                               num_faces=1)
        detector = vision.FaceLandmarker.create_from_options(options)

        image = mp.Image.create_from_file(file_path)

        detection_result = detector.detect(image)
        annotated_image = self.draw_landmarks_on_image(image.numpy_view(), detection_result)
        image_bgr = cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR)

        _, encoded_image = cv2.imencode('.jpg', image_bgr)

        image_base64 = "data:image/jpeg;base64," + base64.b64encode(encoded_image).decode('utf-8')

        return {"imageWithPoints": image_base64}

    def draw_landmarks_on_image(self, rgb_image, detection_result):
        face_landmarks_list = detection_result.face_landmarks
        annotated_image = np.copy(rgb_image)

        # Loop through the detected faces to visualize.
        for idx in range(len(face_landmarks_list)):
            face_landmarks = face_landmarks_list[idx]

            # Draw the face landmarks.
            face_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
            face_landmarks_proto.landmark.extend([
                landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in face_landmarks
            ])

            solutions.drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=face_landmarks_proto,
                connections=mp.solutions.face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles
                .get_default_face_mesh_tesselation_style())
            solutions.drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=face_landmarks_proto,
                connections=mp.solutions.face_mesh.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles
                .get_default_face_mesh_contours_style())
            solutions.drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=face_landmarks_proto,
                connections=mp.solutions.face_mesh.FACEMESH_IRISES,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles
                .get_default_face_mesh_iris_connections_style())

        return annotated_image

    def plot_face_blendshapes_bar_graph(self, face_blendshapes):
        # Extract the face blendshapes category names and scores.
        face_blendshapes_names = [face_blendshapes_category.category_name for face_blendshapes_category in
                                  face_blendshapes]
        face_blendshapes_scores = [face_blendshapes_category.score for face_blendshapes_category in face_blendshapes]
        # The blendshapes are ordered in decreasing score value.
        face_blendshapes_ranks = range(len(face_blendshapes_names))

        fig, ax = plt.subplots(figsize=(12, 12))
        bar = ax.barh(face_blendshapes_ranks, face_blendshapes_scores, label=[str(x) for x in face_blendshapes_ranks])
        ax.set_yticks(face_blendshapes_ranks, face_blendshapes_names)
        ax.invert_yaxis()

        # Label each bar with values
        for score, patch in zip(face_blendshapes_scores, bar.patches):
            plt.text(patch.get_x() + patch.get_width(), patch.get_y(), f"{score:.4f}", va="top")

        ax.set_xlabel('Score')
        ax.set_title("Face Blendshapes")
        plt.tight_layout()
        plt.show()
