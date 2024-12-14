import math
import os
from typing import Tuple, Union, Literal
import mediapipe as mp
import mysql

from app.db.models.Session import SessionResult
from app.services.images_service import get_face_landmarks_detection


class SessionService:
    def __init__(self, db_connection: mysql.connector.MySQLConnection):
        self.connection = db_connection
        self.right_eyebrow_pts = [70, 63, 105, 66, 107, 46, 53, 52, 65, 55]
        self.left_eyebrow_pts = [300, 293, 334, 296, 336, 276, 283, 282, 295, 285]
        self.right_mouth_end_pt = 61
        self.left_mouth_end_pt = 291
        self.paralised_side = None

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
        higher_distance_eyebrow_point_left = self.get_eyebrow_higher_pt_distance(
            [item for item in results_by_expression if any(key in ['Repouso', 'Enrugar testa'] for key in item)], 'left')
        higher_distance_eyebrow_point_right = self.get_eyebrow_higher_pt_distance(
            [item for item in results_by_expression if any(key in ['Repouso', 'Enrugar testa'] for key in item)], 'right')

        left_higher_eyebrow_pt, left_variation_eyebrow_distance = higher_distance_eyebrow_point_left
        right_higher_eyebrow_pt, right_variation_eyebrow_distance = higher_distance_eyebrow_point_right
        self.paralised_side = 'left' if left_variation_eyebrow_distance < right_variation_eyebrow_distance else 'right'


        eyebrow_proportion = (
                                 left_variation_eyebrow_distance if self.paralised_side == 'left' else right_variation_eyebrow_distance) / (
                                 right_variation_eyebrow_distance if self.paralised_side == 'left' else left_variation_eyebrow_distance)

        eyebrow_score = self.calculate_HB_proportion_score(eyebrow_proportion)


        higher_distance_mouth_point_left = self.get_mouth_higher_pt_distance(
            [item for item in results_by_expression if any(key in ['Repouso', 'Sorrir'] for key in item)], 'left')
        higher_distance_mouth_point_right = self.get_mouth_higher_pt_distance(
            [item for item in results_by_expression if any(key in ['Repouso', 'Sorrir'] for key in item)], 'right')
        left_higher_mouth_pt, left_variation_mouth_distance = higher_distance_mouth_point_left
        right_higher_mouth_pt, right_variation_mouth_distance = higher_distance_mouth_point_right

        mouth_proportion = (
                                 left_variation_mouth_distance if self.paralised_side == 'left' else right_variation_mouth_distance) / (
                                 right_variation_mouth_distance if self.paralised_side == 'left' else left_variation_mouth_distance)

        mouth_score = self.calculate_HB_proportion_score(mouth_proportion)

        return self.calculate_HB_total_score(eyebrow_score + mouth_score)

    def calculate_HB_proportion_score(self, proportion: float) -> int:
        if proportion <= 0.25:
            return 0
        elif proportion <= 0.50:
            return 1
        elif proportion <= 0.75:
            return 2
        elif proportion <= 0.89:
            return 3
        elif proportion <= 1.00:
            return 4
        else:
            raise ValueError("Error calculating proportion")

    def calculate_HB_total_score(self, total_score: int) -> str:
        if not (0 <= total_score <= 8):
            raise ValueError("Error calculating total score")

        if total_score <= 1:
            return "Grau VI (Paralisia Total)"
        elif total_score <= 3:
            return "Grau V (Paralisia Severa)"
        elif total_score <= 5:
            return "Grau IV (Paralisia Moderada-Severa)"
        elif total_score == 6:
            return "Grau III (Paralisia Moderada)"
        elif total_score == 7:
            return "Grau II (Paralisia Leve)"
        else:
            return "Grau I (Normal)"

    def get_eyebrow_higher_pt_distance(self, expression_results, side):
        pts = []
        max_distance = 0
        max_point = None

        for item in expression_results:
            for facial_expression, data in item.items():
                pts.append({
                    facial_expression: self._get_eyebrow_px_pts(mp.Image.create_from_file(data.get('file_path')), data.get('result'), side)
                })

        repouso_points = pts[0]['Repouso']
        enrugar_testa_points = pts[1]['Enrugar testa']

        min_length = min(len(repouso_points), len(enrugar_testa_points))

        for i in range(min_length):
            key1, coord1 = list(repouso_points[i].items())[0]
            key2, coord2 = list(enrugar_testa_points[i].items())[0]

            if key1 == key2:
                distance = self._calculate_distance_pixels(coord1, coord2)
                if distance > max_distance:
                    max_distance = distance
                    max_point = key1

        return max_point, max_distance

    def get_mouth_higher_pt_distance(self, expression_results, side):
        pts = []
        max_distance = 0
        max_point = None

        for item in expression_results:
            for facial_expression, data in item.items():
                pts.append({
                    facial_expression: self._get_mouth_px_pts(mp.Image.create_from_file(data.get('file_path')), data.get('result'), side)
                })

        repouso_points = pts[0]['Repouso']
        sorrir_points = pts[1]['Sorrir']

        min_length = min(len(repouso_points), len(sorrir_points))

        for i in range(min_length):
            key1, coord1 = list(repouso_points[i].items())[0]
            key2, coord2 = list(sorrir_points[i].items())[0]

            if key1 == key2:
                distance = self._calculate_distance_pixels(coord1, coord2)
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
        return self.get_px_pts_from_detection_result(self.right_eyebrow_pts if side == 'right' else self.left_eyebrow_pts, image, detection_result)

    def _get_mouth_px_pts(self, image, detection_result, side):
        return self.get_px_pts_from_detection_result([self.right_mouth_end_pt] if side == 'right' else [self.left_mouth_end_pt], image, detection_result)

    def get_px_pts_from_detection_result(self, facelandmark_pts, image, detection_result):
        pts = []
        image_rows, image_cols, _ = image.numpy_view().shape

        for idx2, landmark in enumerate(detection_result.face_landmarks[0]):
            if idx2 in facelandmark_pts:
                pts.append({
                    idx2: self._normalized_to_pixel_coordinates(landmark.x, landmark.y, image_cols, image_rows)
                })
        return pts

    def _calculate_distance_pixels(self, pt1, pt2, type: Literal["euclidian", "horizontal", "vertical"] = "euclidian") -> float:
        x1, y1 = pt1
        x2, y2 = pt2

        if type == "horizontal":
            return abs(x2 - x1)
        elif type == "vertical":
            return abs(y2 - y1)
        elif type == "euclidian":
            return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        else:
            raise ValueError("Invalid distance type")
