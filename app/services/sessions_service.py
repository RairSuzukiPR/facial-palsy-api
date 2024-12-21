import math
import os
from typing import Tuple, Union, Literal, List, Dict
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
        self.paralyzed_side = None

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


    def get_session_images(self, session_id: int):
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("select photo_id, facial_expression from photos as p where p.session_id = %s and p.with_points = FALSE", (session_id,))
        result = cursor.fetchall()
        cursor.close()
        return result

    def process_session(self, session_id: int) -> "SessionResult":
        images = self.get_session_images(session_id)
        results_by_expression = self._process_images(images)

        house_brackmann_score = self.get_house_brackmann_classif(results_by_expression)

        return SessionResult(
            session_id=session_id,
            house_brackmann=house_brackmann_score,
            sunnybrook=20,
            photos=['TBD'],
            photos_with_poitns=['TBD'],
        )

    def _process_images(self, images: List[Dict]) -> List[Dict]:
        current_directory = os.getcwd()
        results = []

        for image in images:
            file_path = os.path.join(current_directory, f"app/assets/{image.get('photo_id')}.jpg")
            results.append({
                image.get('facial_expression'): {
                    "result": get_face_landmarks_detection(file_path),
                    "file_path": file_path,
                }
            })
        return results

    def get_house_brackmann_classif(self, results_by_expression):
        eyebrow_score = self.calculate_HB_eyebrow_score(results_by_expression)
        mouth_score = self.calculate_HB_mouth_score(results_by_expression)

        return self.calculate_HB_total_score(eyebrow_score + mouth_score)

    def calculate_HB_eyebrow_score(self, results_by_expression):
        eyebrow_distance_results = self._calculate_higher_variation_point(
            results_by_expression,
            ['Repouso', 'Enrugar testa'],
            self.left_eyebrow_pts,
            self.right_eyebrow_pts
        )
        self.paralyzed_side = 'left' if eyebrow_distance_results['left']['max_distance'] < \
                                        eyebrow_distance_results['right']['max_distance'] else 'right'

        eyebrow_paralised_max_pt = eyebrow_distance_results[self.paralyzed_side]['max_point']
        eyebrow_paralised_ref_pts = self.left_eyebrow_pts if eyebrow_paralised_max_pt in self.left_eyebrow_pts else self.right_eyebrow_pts
        eyebrow_normal_ref_pts = self.left_eyebrow_pts if eyebrow_paralised_max_pt not in self.left_eyebrow_pts else self.right_eyebrow_pts
        index_paralised_pt_idx = eyebrow_paralised_ref_pts.index(eyebrow_paralised_max_pt)
        normal_eyebrow_pt_sim = eyebrow_normal_ref_pts[index_paralised_pt_idx]

        distances = self._calculate_distance_between_expression_pts(
            results_by_expression,
            ['Repouso', 'Enrugar testa'],
            eyebrow_paralised_max_pt if self.paralyzed_side == 'left' else normal_eyebrow_pt_sim,
            eyebrow_paralised_max_pt if self.paralyzed_side == 'right' else normal_eyebrow_pt_sim,
        )

        paralyzed_side_distance = distances[0 if self.paralyzed_side == 'left' else 1]
        normal_side_distance = distances[1 if self.paralyzed_side == 'left' else 0]

        eyebrow_proportion = paralyzed_side_distance / normal_side_distance
        eyebrow_score = self.calculate_HB_proportion_score(eyebrow_proportion)
        return eyebrow_score

    def calculate_HB_mouth_score(self, results_by_expression):
        distances = self._calculate_distance_between_expression_pts(
            results_by_expression,
            ['Repouso', 'Sorrir'],
            self.left_mouth_end_pt,
            self.right_mouth_end_pt
        )
        paralyzed_side_distance = distances[0 if self.paralyzed_side == 'left' else 1]
        normal_side_distance = distances[1 if self.paralyzed_side == 'left' else 0]

        mouth_proportion = paralyzed_side_distance / normal_side_distance
        mouth_score = self.calculate_HB_proportion_score(mouth_proportion)
        return mouth_score

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

    def _calculate_distance_between_expression_pts(self, results_by_expression, expressions, left_pt, right_pt):
        results = []
        points_by_expression = []
        filtered_items = [item for item in results_by_expression if any(key in expressions for key in item)]

        for side in ['left', 'right']:
            aux = []
            for item in filtered_items:
                for expression, data in item.items():
                    # print(expression, self.get_px_pts_from_detection_result(
                    #             [left_pt] if side == 'left' else [right_pt],
                    #             mp.Image.create_from_file(data.get('file_path')),
                    #             data.get('result')
                    #         )[0])
                    aux.append(
                        next(iter(
                            self.get_px_pts_from_detection_result(
                                [left_pt] if side == 'left' else [right_pt],
                                mp.Image.create_from_file(data.get('file_path')),
                                data.get('result')
                            )[0].values()
                        ))
                   )
            points_by_expression.append(aux)

        for expressions_coords in points_by_expression:
            results.append(self._calculate_distance_pixels(expressions_coords[0], expressions_coords[1]))

        return results

    def _calculate_higher_variation_point(self, results_by_expression, expressions, left_pts, right_pts):
        if len(expressions) != 2:
            raise ValueError("Deve haver exatamente duas expressões para comparar.")

        results = {}

        for side in ['left', 'right']:
            points_by_expression = [
                {
                    expression: self.get_px_pts_from_detection_result(
                        left_pts if side == 'left' else right_pts,
                        mp.Image.create_from_file(data.get('file_path')),
                        data.get('result')
                    )
                    for expression, data in item.items()
                }
                for item in [item for item in results_by_expression if any(key in expressions for key in item)]
            ]

            try:
                expression_1_points = points_by_expression[0][expressions[0]]
                expression_2_points = points_by_expression[1][expressions[1]]
            except (IndexError, KeyError) as e:
                raise ValueError(f"Dados insuficientes para {expressions}") from e

            max_point, max_distance = None, 0
            for points_1, points_2 in zip(expression_1_points, expression_2_points):
                (key1, coord1), (key2, coord2) = list(points_1.items())[0], list(points_2.items())[0]

                if key1 == key2:
                    distance = self._calculate_distance_pixels(coord1, coord2)
                    if distance > max_distance:
                        max_distance = distance
                        max_point = key1

            results[side] = {'max_point': max_point, 'max_distance': max_distance}

        return results

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

    def get_px_pts_from_detection_result(self, facelandmark_pts, image, detection_result):
        pts = []
        image_rows, image_cols, _ = image.numpy_view().shape

        for idx2, landmark in enumerate(detection_result.face_landmarks[0]):
            if idx2 in facelandmark_pts:
                # print('->', idx2, self._normalized_to_pixel_coordinates(landmark.x, landmark.y, image_cols, image_rows))
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
