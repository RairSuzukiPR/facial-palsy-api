import base64
import io
import os
import shutil
import cv2
import mediapipe as mp
import mysql
import math
from fastapi import UploadFile, File
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
from typing import Tuple, Union, List, Dict
import numpy as np
import uuid
from PIL import Image


def get_face_landmarks_detection(file_path):
    base_options = python.BaseOptions(model_asset_path='./face_landmarker_v2_with_blendshapes.task')
    options = vision.FaceLandmarkerOptions(base_options=base_options,
                                           output_face_blendshapes=True,
                                           output_facial_transformation_matrixes=True,
                                           num_faces=1)
    detector = vision.FaceLandmarker.create_from_options(options)

    image = mp.Image.create_from_file(file_path)

    return detector.detect(image)

def _normalized_to_pixel_coordinates(normalized_x: float, normalized_y: float, image_width: int,
                                     image_height: int) -> Union[None, Tuple[int, int]]:
    """Converts normalized value pair to pixel coordinates."""

    def is_valid_normalized_value(value: float) -> bool:
        return (value > 0 or math.isclose(0, value)) and (value < 1 or
                                                          math.isclose(1, value))

    if not (is_valid_normalized_value(normalized_x) and
            is_valid_normalized_value(normalized_y)):
        return None

    x_px = min(math.floor(normalized_x * image_width), image_width - 1)
    y_px = min(math.floor(normalized_y * image_height), image_height - 1)
    return x_px, y_px


def get_px_pts_from_detection_result(facelandmark_pts, image, detection_result):
    pts = []
    image_rows, image_cols, _ = image.numpy_view().shape
    if not len(detection_result.face_landmarks):
        raise KeyError('Pontos faciais nao detectados')
    for idx2, landmark in enumerate(detection_result.face_landmarks[0]):
        if idx2 in facelandmark_pts:
            # print('->', idx2, _normalized_to_pixel_coordinates(landmark.x, landmark.y, image_cols, image_rows))
            pts.append({
                idx2: _normalized_to_pixel_coordinates(landmark.x, landmark.y, image_cols, image_rows)
            })
    return pts


class ImagesService:
    def __init__(self, db_connection: mysql.connector.MySQLConnection):
        self.connection = db_connection
        self.face_border_pts = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 401, 361, 288, 397, 365, 379, 378, 400,
                                377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 45, 103, 67,
                                109]

    def classify_image(self, file: UploadFile = File(...)):
        image_uuid = str(uuid.uuid4())
        image_with_points_uuid = str(uuid.uuid4())
        # image_uuid = '$1aaa'
        # image_with_points_uuid = '1bbb'

        current_directory = os.getcwd()
        file_path = os.path.join(current_directory, f"app/assets/{image_uuid}.jpg")
        # file_path = os.path.join(current_directory, f"app/assets/$2aaa.jpg")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        self._pre_process_image(file_path)

        detection_result = get_face_landmarks_detection(file_path)

        image = mp.Image.create_from_file(file_path)
        annotated_image = self._draw_landmarks_on_image(image.numpy_view(), detection_result)
        image_bgr = cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR)

        _, encoded_image = cv2.imencode('.jpg', image_bgr)

        # image_base64 = "data:image/jpeg;base64," + base64.b64encode(encoded_image).decode('utf-8')
        file_path_with_points = os.path.join(current_directory, f"app/assets/${image_with_points_uuid}.jpg")
        # file_path_with_points = os.path.join(current_directory, f"app/assets/$2bbb.jpg")
        encoded_image_buffer = io.BytesIO(encoded_image.tobytes())
        with open(file_path_with_points, "wb") as buffer:
            shutil.copyfileobj(encoded_image_buffer, buffer)
        # original_image_base64 = "data:image/jpeg;base64," + base64.b64encode(image).decode('utf-8')
        # image_base64 = "data:image/jpeg;base64," + base64.b64encode(encoded_image).decode('utf-8')

        return {
            "image": image_uuid,
            "image_with_points": image_with_points_uuid
        }

    def insert_images_db(self, image_id, session_id, image_url, facial_expression, with_points):
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                    INSERT INTO photos (photo_id, session_id, photo_url, facial_expression, with_points)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                (image_id, session_id, image_url, facial_expression, with_points)
            )
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()

    def _pre_process_image(self, file_path):
        all_pts = get_px_pts_from_detection_result(
            self.face_border_pts,
            mp.Image.create_from_file(file_path),
            get_face_landmarks_detection(file_path)
        )
        # print(self._get_face_limits(all_pts))
        self.crop_face_image(self._get_face_limits(all_pts), file_path)

    def _get_face_limits(self, coordinates: List[Dict[int, Tuple[int, int]]]) -> list[tuple[int, int]]:
        keypoints = {key: value for point in coordinates for key, value in point.items()}

        higher_vert = min(keypoints.items(), key=lambda x: x[1][1])
        lower_vert = max(keypoints.items(), key=lambda x: x[1][1])
        higher_horiz = min(keypoints.items(), key=lambda x: x[1][0])
        lower_horiz = max(keypoints.items(), key=lambda x: x[1][0])

        return [higher_horiz[1], higher_vert[1], lower_horiz[1], lower_vert[1]]

    def crop_face_image(self, coordinates: List[Tuple[int, int]], file_path: str, offset_x_pct: float = 0.2,
                        offset_y_pct: float = 0.2) -> None:
        if len(coordinates) != 4:
            raise ValueError("O array de coordenadas deve conter exatamente 4 pontos.")

        with Image.open(file_path) as img:
            width, height = img.size
            offset_x = int(width * offset_x_pct)
            offset_y = int(height * offset_y_pct)

            min_x = min(p[0] for p in coordinates) - offset_x
            max_x = max(p[0] for p in coordinates) + offset_x
            min_y = min(p[1] for p in coordinates) - offset_y
            max_y = max(p[1] for p in coordinates) + offset_y

            cropped_img = img.crop((min_x, min_y, max_x, max_y))
            cropped_img.save(file_path)

    def _draw_landmarks_on_image(self, rgb_image, detection_result):
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
