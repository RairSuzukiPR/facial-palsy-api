import math
import os
from typing import Tuple, Union
import mediapipe as mp
import mysql

from app.db.models.Session import SessionResult
from app.services.images_service import get_face_landmarks_detection


class SessionService:
    def __init__(self, db_connection: mysql.connector.MySQLConnection):
        self.right_eyebrow_pts = [70, 63, 105, 66, 107, 46, 53, 52, 65, 55]
        self.left_eyebrow_pts = [336, 296, 334, 293, 300, 285, 295, 282, 283, 276]
        self.connection = db_connection

    def new_session(self, user_id: int):
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                """
                    INSERT INTO sessions (user_id)
                    VALUES (%s)
                """,
                (user_id,)
            )
            self.connection.commit()

            return {
                "session_id": cursor.lastrowid
            }
        except Exception as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()


    def process_session(self, session_id: int):
        images = self.get_session_images(session_id)
        results_by_expression = []

        for image in images:
            current_directory = os.getcwd()
            file_path = os.path.join(current_directory, f"app/assets/{image.get('photo_id')}.jpg")
            results_by_expression.append({
                image.get('facial_expression'): {
                    "result": get_face_landmarks_detection(file_path),
                    "file_path": file_path
                }
            })

        house_brackmann_score = self.get_house_brackmann_classif(results_by_expression)

        return SessionResult(
            session_id=session_id,
            house_brackmann=house_brackmann_score,
            sunnybrook=20,
            photos=['TBD'],
            photos_with_poitns=['TBD'],
        )


    def get_session_images(self, session_id: int):
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("select photo_id, facial_expression from photos as p where p.session_id = %s and p.with_points = FALSE", (session_id,))
        result = cursor.fetchall()
        cursor.close()
        return result

    def get_house_brackmann_classif(self, results_by_expression):
        # TODO filtrar aq exp necessarias pra house b
        higher_eyebrow_point_left = self.get_eyebrow_higher_pt(
            [item for item in results_by_expression if any(key in ['Repouso', 'Enrugar testa'] for key in item)], 'left')
        higher_eyebrow_point_right = self.get_eyebrow_higher_pt(
            [item for item in results_by_expression if any(key in ['Repouso', 'Enrugar testa'] for key in item)], 'right')

        print(higher_eyebrow_point_left)
        print(higher_eyebrow_point_right)
        return 'IV'

    def get_eyebrow_higher_pt(self, expression_results, side):
        pts = []

        for item in expression_results:
            for facial_expression, data in item.items():
                pts.append({
                    facial_expression: self._get_eyebrow_px_pts(mp.Image.create_from_file(data.get('file_path')), data.get('result'), side)
                })

        return self.find_max_variation_pt(pts)

    def find_max_variation_pt(self, data):
        repouso_points = data[0]['Repouso']
        enrugar_testa_points = data[1]['Enrugar testa']

        min_length = min(len(repouso_points), len(enrugar_testa_points))

        max_distance = 0
        max_point = None

        for i in range(min_length):
            key1, coord1 = list(repouso_points[i].items())[0]
            key2, coord2 = list(enrugar_testa_points[i].items())[0]

            if key1 == key2:
                distance = self._euclidean_distance_pixels(coord1, coord2)
                if distance > max_distance:
                    max_distance = distance
                    max_point = key1

        return max_point, max_distance

    def _normalized_to_pixel_coordinates(self,
            normalized_x: float, normalized_y: float, image_width: int,
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

    def _get_eyebrow_px_pts(self, image, detection_result, side):
        facelandmark_pts = self.right_eyebrow_pts if side == 'right' else self.left_eyebrow_pts
        pts = []
        image_rows, image_cols, _ = image.numpy_view().shape

        for idx2, landmark in enumerate(detection_result.face_landmarks[0]):
            if idx2 in facelandmark_pts:
                pts.append({
                    idx2: self._normalized_to_pixel_coordinates(landmark.x, landmark.y, image_cols, image_rows)
                })
        return pts

    def _euclidean_distance_pixels(self, p1, p2):
        return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)
