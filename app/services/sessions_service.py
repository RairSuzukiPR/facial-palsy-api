import datetime
import math
import os
from typing import Tuple, Union, Literal, List, Dict
import mediapipe as mp
import mysql
from PIL import Image
import io
import base64
from app.db.models.Session import SessionResult
from app.services.images_service import get_face_landmarks_detection, get_px_pts_from_detection_result


class SessionService:
    def __init__(self, db_connection: mysql.connector.MySQLConnection):
        self.connection = db_connection
        self.paralyzed_side = None

        self.hb_eyes_simetry = -1
        self.hb_mouth_simetry = -1
        self.sb_forehead_wrinkle_simetry = -1
        self.sb_gentle_eye_closure_simetry = -1
        self.sb_smile_simetry = -1
        self.sb_snarl_simetry = -1
        self.sb_lip_pucker_simetry = -1

        self.synkinesis_eyebrows = False
        self.synkinesis_eyes = False
        self.synkinesis_mouth = False
        self.mouth_synkinesis_by_raising_eyebrows = False
        self.eyebrows_synkinesis_by_closing_eyes = False
        self.mouth_synkinesis_by_closing_eyes = False
        self.eyebrows_synkinesis_by_smiling = False
        self.eyes_synkinesis_by_smiling = False
        self.eyes_synkinesis_by_snarl = False
        self.eyebrows_synkinesis_by_lip_pucker = False
        self.eyes_synkinesis_by_lip_pucker = False

        self.mid_forhead_pt = 10
        self.right_eyebrow_pts = [70, 63, 105, 66, 107, 46, 53, 52, 65, 55]
        self.left_eyebrow_pts = [300, 293, 334, 296, 336, 276, 283, 282, 295, 285]
        self.average_line_pt = 168
        self.mid_mouth_end_pt = 13
        self.right_mouth_end_pt = 61
        self.left_mouth_end_pt = 291
        self.right_eye_open_pts = [159, 145]
        self.left_eye_open_pts = [386, 374]
        self.alar_base_pts = [48, 278]
        self.right_mouth_lip_p_pts = [58, 61]
        self.left_mouth_lip_p_pts = [288, 291]


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

    def get_sessions(self, user_id):
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                s.session_id,
                p.photo_id,    
                hb_eyes_simetry,
                hb_mouth_simetry,
                sb_forehead_wrinkle_simetry,
                sb_gentle_eye_closure_simetry,
                sb_smile_simetry,
                sb_snarl_simetry,
                sb_lip_pucker_simetry,
                eyes_synkinesis,
                eyebrows_synkinesis,
                mouth_synkinesis, 
                mouth_synkinesis_by_raising_eyebrows, 
                eyebrows_synkinesis_by_closing_eyes,
                mouth_synkinesis_by_closing_eyes, 
                eyebrows_synkinesis_by_smiling, 
                eyes_synkinesis_by_smiling,
                eyes_synkinesis_by_snarl, 
                eyebrows_synkinesis_by_lip_pucker, 
                eyes_synkinesis_by_lip_pucker,    
                house_brackmann,
                sunnybrook,
                processed_at
            FROM `facial-palsy-db`.results as r
                join `facial-palsy-db`.sessions as s
                    on s.session_id = r.session_id
                join `facial-palsy-db`.photos as p
                    on s.session_id = p.session_id 
            where s.user_id = %s;
        """, (user_id,))
        result = cursor.fetchall()
        cursor.close()
        return result

    def end_session(self, session_id, house_brackmann, sunnybrook):
        cursor = self.connection.cursor()
        try:
            query = """
                    INSERT INTO results (
                        session_id, house_brackmann, sunnybrook, hb_eyes_simetry, hb_mouth_simetry,
                        sb_forehead_wrinkle_simetry, sb_gentle_eye_closure_simetry, sb_smile_simetry,
                        sb_snarl_simetry, sb_lip_pucker_simetry, eyes_synkinesis, eyebrows_synkinesis,
                        mouth_synkinesis, mouth_synkinesis_by_raising_eyebrows, eyebrows_synkinesis_by_closing_eyes,
                        mouth_synkinesis_by_closing_eyes, eyebrows_synkinesis_by_smiling, eyes_synkinesis_by_smiling,
                        eyes_synkinesis_by_snarl, eyebrows_synkinesis_by_lip_pucker, eyes_synkinesis_by_lip_pucker
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """

            values = (session_id, house_brackmann, sunnybrook, self.hb_eyes_simetry, self.hb_mouth_simetry,
                      self.sb_forehead_wrinkle_simetry, self.sb_gentle_eye_closure_simetry, self.sb_smile_simetry,
                      self.sb_snarl_simetry, self.sb_lip_pucker_simetry, self.synkinesis_eyes, self.synkinesis_eyebrows,
                      self.synkinesis_mouth, self.mouth_synkinesis_by_raising_eyebrows,
                      self.eyebrows_synkinesis_by_closing_eyes,
                      self.mouth_synkinesis_by_closing_eyes, self.eyebrows_synkinesis_by_smiling,
                      self.eyes_synkinesis_by_smiling,
                      self.eyes_synkinesis_by_snarl, self.eyebrows_synkinesis_by_lip_pucker,
                      self.eyes_synkinesis_by_lip_pucker)
            cursor.execute(query, values)
            self.connection.commit()
            return
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

    def process_session(self, user, session_id: int) -> SessionResult:
        images = self.get_session_images(session_id)
        results_by_expression = self._process_images(images)

        house_brackmann_score = self.get_house_brackmann_classif(results_by_expression)
        sunnybrook_score = self.get_sunnybrook_classif(results_by_expression, user)

        imagesB64 = []
        for item in images:
            photo_path = os.path.join(os.getcwd(), f"app/assets/{item['photo_id']}.jpg")
            base64_image = self.file_to_base64(photo_path, compression_level=30)
            if base64_image:
                imagesB64.append("data:image/jpeg;base64," + base64_image)

        self.end_session(session_id, house_brackmann_score, sunnybrook_score)
        return SessionResult(
            session_id=session_id,
            house_brackmann=house_brackmann_score,
            sunnybrook=sunnybrook_score,
            # house_brackmann="I",
            # sunnybrook='90',
            hb_eyes_simetry=self.hb_eyes_simetry,
            hb_mouth_simetry=self.hb_mouth_simetry,
            sb_forehead_wrinkle_simetry=self.sb_forehead_wrinkle_simetry,
            sb_gentle_eye_closure_simetry=self.sb_gentle_eye_closure_simetry,
            sb_smile_simetry=self.sb_smile_simetry,
            sb_snarl_simetry=self.sb_snarl_simetry,
            sb_lip_pucker_simetry=self.sb_lip_pucker_simetry,
            eyes_synkinesis=self.synkinesis_eyes,
            eyebrows_synkinesis=self.synkinesis_eyebrows,
            mouth_synkinesis=self.synkinesis_mouth,
            mouth_synkinesis_by_raising_eyebrows=self.mouth_synkinesis_by_raising_eyebrows,
            eyebrows_synkinesis_by_closing_eyes=self.eyebrows_synkinesis_by_closing_eyes,
            mouth_synkinesis_by_closing_eyes=self.mouth_synkinesis_by_closing_eyes,
            eyebrows_synkinesis_by_smiling=self.eyebrows_synkinesis_by_smiling,
            eyes_synkinesis_by_smiling=self.eyes_synkinesis_by_smiling,
            eyes_synkinesis_by_snarl=self.eyes_synkinesis_by_snarl,
            eyebrows_synkinesis_by_lip_pucker=self.eyebrows_synkinesis_by_lip_pucker,
            eyes_synkinesis_by_lip_pucker=self.eyes_synkinesis_by_lip_pucker,
            processed_at=datetime.datetime.now(),
            photos=imagesB64,
            # photos_with_poitns=['TBD'],
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
        print('\nHB eyebrow_score', eyebrow_score)
        print('HB mouth_score', mouth_score)
        self.hb_eyes_simetry = self.calculate_HB_simetry_score(eyebrow_score)
        self.hb_mouth_simetry = self.calculate_HB_simetry_score(mouth_score)

        return self.calculate_HB_total_score(eyebrow_score + mouth_score)

    def calculate_HB_eyebrow_score(self, results_by_expression):
        # print('\ncalculate_HB_eyebrow_score')
        highest_pts, lowest_pts = self._calculate_highest_and_lowest_eyebrow_point(results_by_expression, 'Enrugar testa', self.left_eyebrow_pts, self.right_eyebrow_pts)
        # print('highest_pts', highest_pts)
        # print('lowest_pts', lowest_pts)

        paralyzed_side_highest_pt = highest_pts[0 if self.paralyzed_side == 'left' else 1]
        normal_side_highest_pt = highest_pts[1 if self.paralyzed_side == 'left' else 0]
        paralyzed_side_lowest_pt = lowest_pts[0 if self.paralyzed_side == 'left' else 1]
        normal_side_lowest_pt = lowest_pts[1 if self.paralyzed_side == 'left' else 0]
        # print('self.paralyzed_side', self.paralyzed_side)
        # print('paralyzed_side_highest_pt', paralyzed_side_highest_pt)
        # print('normal_side_highest_pt', normal_side_highest_pt)
        # print('paralyzed_side_lowest_pt', paralyzed_side_lowest_pt)
        # print('normal_side_lowest_pt', normal_side_lowest_pt)

        normal_eyebrow_range_distance = self._calculate_distance_pixels(normal_side_highest_pt, normal_side_lowest_pt, 'horizontal')
        # print('normal_eyebrow_range_distance', normal_eyebrow_range_distance)
        paralyzed_eyebrow_range_distance = self._calculate_distance_pixels(paralyzed_side_highest_pt, normal_side_lowest_pt, 'horizontal')
        # print('paralyzed_eyebrow_range_distance', paralyzed_eyebrow_range_distance)

        return self._calculate_HB_proportion_score(normal_eyebrow_range_distance, paralyzed_eyebrow_range_distance)

        # eyebrow_proportion = normal_side_highest_pt / paralyzed_side_highest_pt
        # # eyebrow_proportion = abs(normal_side_pt - paralyzed_side_pt) / normal_side_pt
        # print('-> eyebrow_proportion', eyebrow_proportion)
        #
        # eyebrow_score = self.calculate_HB_proportion_score(eyebrow_proportion)
        # print('eyebrow_score', eyebrow_score)
        # return eyebrow_score

        # forma q verif variacao
        # eyebrow_distance_results = self._calculate_higher_variation_point(
        #     results_by_expression,
        #     ['Repouso', 'Enrugar testa'],
        #     self.left_eyebrow_pts,
        #     self.right_eyebrow_pts
        # )
        # print('eyebrow_distance_results', eyebrow_distance_results)
        # # nao sei se é a melhor forma de verificar isso (visto q pode puxar diferentes pontos da sobrancelha)
        # self.paralyzed_side = 'left' if eyebrow_distance_results['left']['max_distance'] < eyebrow_distance_results['right']['max_distance'] else 'right'
        #
        # eyebrow_paralised_max_pt = eyebrow_distance_results[self.paralyzed_side]['max_point']
        # eyebrow_paralised_ref_pts = self.left_eyebrow_pts if eyebrow_paralised_max_pt in self.left_eyebrow_pts else self.right_eyebrow_pts
        # eyebrow_normal_ref_pts = self.left_eyebrow_pts if eyebrow_paralised_max_pt not in self.left_eyebrow_pts else self.right_eyebrow_pts
        # index_paralised_pt_idx = eyebrow_paralised_ref_pts.index(eyebrow_paralised_max_pt)
        # normal_eyebrow_pt_sim = eyebrow_normal_ref_pts[index_paralised_pt_idx]
        # # print('eyebrow_distance_results', eyebrow_distance_results)
        # print('self.paralyzed_side', self.paralyzed_side)
        # print('aaa', eyebrow_paralised_max_pt if self.paralyzed_side == 'left' else normal_eyebrow_pt_sim)
        # print('bbb', eyebrow_paralised_max_pt if self.paralyzed_side == 'right' else normal_eyebrow_pt_sim)
        # print('eyebrow_normal_ref_pts', eyebrow_normal_ref_pts)
        # print('index_paralised_pt_idx', index_paralised_pt_idx)
        # print('normal_eyebrow_pt_sim', normal_eyebrow_pt_sim)
        #
        # distances = self._calculate_distance_between_expression_pts(
        #     results_by_expression,
        #     ['Repouso', 'Enrugar testa'],
        #     eyebrow_paralised_max_pt if self.paralyzed_side == 'left' else normal_eyebrow_pt_sim,
        #     eyebrow_paralised_max_pt if self.paralyzed_side == 'right' else normal_eyebrow_pt_sim,
        #     'vertical'
        # )
        # print('distances', distances)
        #
        # paralyzed_side_distance = distances[0 if self.paralyzed_side == 'left' else 1]
        # normal_side_distance = distances[1 if self.paralyzed_side == 'left' else 0]
        # # paralyzed_side_distance = min(distances[0], distances[1])
        # # normal_side_distance = max(distances[0], distances[1])
        # print('paralyzed_side_distance', paralyzed_side_distance)
        # print('normal_side_distance', normal_side_distance)
        #
        # eyebrow_proportion = paralyzed_side_distance / normal_side_distance
        # print('eyebrow_proportion', eyebrow_proportion)
        # eyebrow_score = self.calculate_HB_proportion_score(eyebrow_proportion)
        # print('eyebrow_score', eyebrow_score)
        # return eyebrow_score

    def calculate_HB_mouth_score(self, results_by_expression):
        # print('\ncalculate_HB_mouth_score')

        range_distances = self._calculate_distance_from_expression_pts(
            results_by_expression,
            ['Sorrir mostrando os dentes'],
            [self.left_mouth_end_pt, self.mid_mouth_end_pt],
            [self.right_mouth_end_pt, self.mid_mouth_end_pt],
            'vertical'
        )
        # print('---> range_distances', range_distances)
        return self._calculate_HB_proportion_score(range_distances[0], range_distances[1])


        # distances = self._calculate_distance_between_expression_pts(
        #     results_by_expression,
        #     ['Repouso', 'Sorrir mostrando os dentes'],
        #     self.left_mouth_end_pt,
        #     self.right_mouth_end_pt,
        #     'vertical'
        # )
        # paralyzed_side_distance = distances[0 if self.paralyzed_side == 'left' else 1]
        # normal_side_distance = distances[1 if self.paralyzed_side == 'left' else 0]
        # print('self.paralyzed_side', self.paralyzed_side)
        # print('distances', distances)
        # print('paralyzed_side_distance', paralyzed_side_distance)
        # print('normal_side_distance', normal_side_distance)
        #
        # mouth_proportion = paralyzed_side_distance / normal_side_distance
        # # mouth_proportion = abs(normal_side_distance - paralyzed_side_distance) / normal_side_distance
        # mouth_score = self.calculate_HB_proportion_score(mouth_proportion)
        # print('mouth_proportion', mouth_proportion)
        # # print('mouth_proportion_test', mouth_proportion_test)
        # # print('teste mouth_proportion', abs(normal_side_distance - paralyzed_side_distance) / normal_side_distance)
        # print('mouth_score', mouth_score)
        # return mouth_score

    def _calculate_HB_proportion_score(self, d1, d2):
        interval = d1 / 5
        var = abs(d1 - d2)

        if var <= interval:
            return 4  # 0 a 25%
        elif var <= 2 * interval:
            return 3  # 25% a 50%
        elif var <= 3 * interval:
            return 2  # 50% a 75%
        elif var <= 4 * interval:
            return 1  # 75% a 100%
        else:
            return 0  # Fora do intervalo

    # def calculate_HB_proportion_score(self, proportion: float) -> int:
    #     if proportion <= 0.25:
    #         return 0
    #     elif proportion <= 0.50:
    #         return 1
    #     elif proportion <= 0.75:
    #         return 2
    #     elif proportion <= 0.89:
    #         return 3
    #     elif proportion <= 1.00:
    #         return 4
    #     else:
    #         raise ValueError("Error calculating proportion")

    def calculate_HB_simetry_score(self, proportion: float) -> int:
        if proportion == 0:
            return 0
        elif proportion == 1:
            return 25
        elif proportion == 2:
            return 50
        elif proportion == 3:
            return 75
        elif proportion == 4:
            return 100

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

    def get_sunnybrook_classif(self, results_by_expression, user):
        rest_symmetry_score = self.calculate_SB_rest_symmetry_score(results_by_expression, user)
        print('\nrest_symmetry_score', rest_symmetry_score)
        movement_symmetry_score = self.calculate_SB_movement_symmetry_score(results_by_expression)
        print('\nmovement_symmetry_score', movement_symmetry_score)
        synkinesis_score = self.calculate_SB_synkinesis_score(results_by_expression)
        print('\nsynkinesis_score', synkinesis_score)

        # TODO: VALIDAR
        return movement_symmetry_score - rest_symmetry_score - synkinesis_score

    def calculate_SB_rest_symmetry_score(self, results_by_expression, user):
        if user.get('eyelid_surgery'):
            eye_score = 1
        else :
            distances_eyes = self._calculate_distance_from_expression_pts(
                results_by_expression,
                ['Repouso'],
                self.left_eye_open_pts,
                self.right_eye_open_pts
            )
            # print('distances_eyes', distances_eyes)
            paralyzed_side_distance_eyes = distances_eyes[0 if self.paralyzed_side == 'left' else 1]
            normal_side_distance_eyes = distances_eyes[1 if self.paralyzed_side == 'left' else 0]
            # print('paralyzed_side_distance_eyes', paralyzed_side_distance_eyes)
            # print('normal_side_distance_eyes', normal_side_distance_eyes)
            perc_variation_eyes = abs(normal_side_distance_eyes - paralyzed_side_distance_eyes) / normal_side_distance_eyes * 100
            eye_score = 1 if perc_variation_eyes > 20 else 0
            # print('perc_variation_eyes', perc_variation_eyes)
            # print('eye_score', eye_score)

        cheeks_score = 0
        if user.get('nasolabial_fold'):
            if user.get('nasolabial_fold_only_paralyzed_side'):
                cheeks_score = 2
            else: cheeks_score = 1

        distances_mouth = self._calculate_distance_mouth_variation(
            results_by_expression,
            ['Repouso'],
            self.left_mouth_end_pt,
            self.right_mouth_end_pt,
            self.average_line_pt
        )
        # print('distances_mouth', distances_mouth)
        perc_variation_mouth = abs(distances_mouth[0] - distances_mouth[1]) / distances_mouth[0] * 100
        mouth_score = 1 if perc_variation_mouth > 20 else 0
        # print('perc_variation_mouth', distances_mouth, perc_variation_mouth, mouth_score)

        return (eye_score + cheeks_score + mouth_score) * 5

    def calculate_SB_movement_symmetry_score(self, results_by_expression):
        forehead_wrinkle_score, _ = self._calculate_SB_forehead_wrinkle_score(results_by_expression, 'Enrugar testa')
        # print('forehead_wrinkle_score', forehead_wrinkle_score)

        gentle_eye_closure_score, _ = self._calculate_SB_gentle_eye_closure_score(results_by_expression, 'Fechar os olhos sem apertar')
        # print('gentle_eye_closure_score', gentle_eye_closure_score)

        open_mouth_smile_score, _ = self._calculate_SB_open_mouth_smile_score(results_by_expression, 'Sorrir mostrando os dentes')
        # print('open_mouth_smile_score', open_mouth_smile_score)

        snarl_score = self._calculate_SB_snarl_score(results_by_expression)
        # print('snarl_score', snarl_score)

        lip_pucker_score = self._calculate_SB_lip_pucker_score(results_by_expression)
        # print('lip_pucker_score', lip_pucker_score)

        self.sb_forehead_wrinkle_simetry = self.calculate_SB_movement_simetry_score(forehead_wrinkle_score)
        self.sb_gentle_eye_closure_simetry = self.calculate_SB_movement_simetry_score(gentle_eye_closure_score)
        self.sb_smile_simetry = self.calculate_SB_movement_simetry_score(open_mouth_smile_score)
        self.sb_snarl_simetry = self.calculate_SB_movement_simetry_score(snarl_score)
        self.sb_lip_pucker_simetry = self.calculate_SB_movement_simetry_score(lip_pucker_score)
        # print('self.sb_forehead_wrinkle_simetry', self.sb_forehead_wrinkle_simetry)
        # print('self.sb_gentle_eye_closure_simetry', self.sb_gentle_eye_closure_simetry)
        # print('self.sb_smile_simetry', self.sb_smile_simetry)
        # print('self.sb_snarl_simetry', self.sb_snarl_simetry)
        # print('self.sb_lip_pucker_simetry', self.sb_lip_pucker_simetry)

        return (forehead_wrinkle_score + gentle_eye_closure_score + open_mouth_smile_score + snarl_score + lip_pucker_score) * 4

    def calculate_SB_movement_percentage_score(self, variation_percentage: float) -> int:
        if not (0 <= variation_percentage <= 100):
            raise ValueError("Error calculating SB percentage score")

        if variation_percentage <= 20:
            return 5
        elif variation_percentage <= 40:
            return 4
        elif variation_percentage <= 60:
            return 3
        elif variation_percentage <= 80:
            return 2
        else:
            return 1

    def calculate_SB_movement_simetry_score(self, value: float) -> int:
        if not (0 <= value <= 100):
            raise ValueError("Error calculating SB simetry score")

        if value == 5:
            return 100
        elif value == 4:
            return 80
        elif value == 3:
            return 40
        elif value == 2:
            return 20
        else:
            return 0

    def calculate_SB_synkinesis_percentage_score(self, variation_percentage: float) -> int:
        if not (0 <= variation_percentage <= 100):
            raise ValueError("Error calculating SB synkinesis percentage score")

        if variation_percentage <= 20:
            return 0
        elif variation_percentage <= 40:
            return 1
        elif variation_percentage <= 61:
            return 2
        else:
            return 3

    def calculate_SB_synkinesis_score(self, results_by_expression):
        # ao enrugar testa analisar boca
        _, open_mouth_smile_forehead_wrinkle_var = self._calculate_SB_open_mouth_smile_score(results_by_expression, 'Enrugar testa')
        # print('open_mouth_smile_forehead_wrinkle_var', open_mouth_smile_forehead_wrinkle_var)
        forehead_wrinkle_score = self.calculate_SB_synkinesis_percentage_score(open_mouth_smile_forehead_wrinkle_var)
        # print('->forehead_wrinkle_score', forehead_wrinkle_score)
        self.mouth_synkinesis_by_raising_eyebrows = True if open_mouth_smile_forehead_wrinkle_var > 20 else False

        # ao fechar os olhos, analisar testa e boca
        _, eyebrows_eyes_closing_var = self._calculate_SB_forehead_wrinkle_score(results_by_expression,
                                                                                 'Fechar os olhos sem apertar',
                                                                                 'Repouso')
        self.eyebrows_synkinesis_by_closing_eyes = True if eyebrows_eyes_closing_var > 20 else False
        # print('eyebrows_eyes_closing_var', eyebrows_eyes_closing_var)
        _, open_mouth_smile_eyes_closure_var = self._calculate_SB_open_mouth_smile_score(results_by_expression, 'Fechar os olhos sem apertar')
        self.mouth_synkinesis_by_closing_eyes = True if open_mouth_smile_eyes_closure_var > 20 else False
        # print('open_mouth_smile_eyes_closure_var', open_mouth_smile_eyes_closure_var)
        gentle_eye_closure_score = self.calculate_SB_synkinesis_percentage_score(max(eyebrows_eyes_closing_var, open_mouth_smile_eyes_closure_var))
        # print('->gentle_eye_closure_score', gentle_eye_closure_score)

        # ao sorrir, analisar testa e olhos
        _, eyebrows_smile_var = self._calculate_SB_forehead_wrinkle_score(results_by_expression,
                                                                          'Sorrir mostrando os dentes', 'Repouso')
        self.eyebrows_synkinesis_by_smiling = True if eyebrows_smile_var > 20 else False
        # print('eyebrows_smile_var', eyebrows_smile_var)
        _, gentle_eye_closure_smile_var = self._calculate_SB_gentle_eye_closure_score(results_by_expression,
                                                                                      'Sorrir mostrando os dentes',
                                                                                      'Repouso')
        self.eyes_synkinesis_by_smiling = True if gentle_eye_closure_smile_var > 20 else False
        # print('gentle_eye_closure_smile_var', gentle_eye_closure_smile_var)
        open_mouth_smile_score = self.calculate_SB_synkinesis_percentage_score(max(eyebrows_smile_var, gentle_eye_closure_smile_var))
        # print('->open_mouth_smile_score', open_mouth_smile_score)

        # ao elevar o labio superior, analisar olhos
        _, gentle_eye_closure_snarl_var = self._calculate_SB_gentle_eye_closure_score(results_by_expression,
                                                                                      'Elevar o lábio superior',
                                                                                      'Repouso')
        self.eyes_synkinesis_by_snarl = True if gentle_eye_closure_snarl_var > 20 else False
        # print('gentle_eye_closure_snarl_var', gentle_eye_closure_snarl_var)
        snarl_score = self.calculate_SB_synkinesis_percentage_score(gentle_eye_closure_snarl_var)
        # print('->snarl_score', snarl_score)

        # ao assobiar, analisar testa e olhos
        _, eyebrows_lip_pucker_var = self._calculate_SB_forehead_wrinkle_score(results_by_expression, 'Assobiar',
                                                                               'Repouso')
        self.eyebrows_synkinesis_by_lip_pucker = True if eyebrows_lip_pucker_var > 20 else False
        # print('eyebrows_lip_pucker_var', eyebrows_lip_pucker_var)
        _, gentle_eye_closure_lip_pucker_var = self._calculate_SB_gentle_eye_closure_score(results_by_expression,
                                                                                      'Assobiar',
                                                                                      'Repouso')
        self.eyes_synkinesis_by_lip_pucker = True if gentle_eye_closure_lip_pucker_var > 20 else False
        lip_pucker_score = self.calculate_SB_synkinesis_percentage_score(max(eyebrows_lip_pucker_var, gentle_eye_closure_lip_pucker_var))
        # print('->lip_pucker_score', lip_pucker_score)

        if self.mouth_synkinesis_by_raising_eyebrows or self.mouth_synkinesis_by_closing_eyes:
            self.synkinesis_mouth = True
        if self.eyebrows_synkinesis_by_closing_eyes or self.eyebrows_synkinesis_by_smiling or self.eyebrows_synkinesis_by_lip_pucker:
            self.synkinesis_eyebrows = True
        if self.eyes_synkinesis_by_smiling or self.eyes_synkinesis_by_snarl or self.eyes_synkinesis_by_lip_pucker:
            self.synkinesis_eyes = True

        return forehead_wrinkle_score + gentle_eye_closure_score + open_mouth_smile_score + snarl_score + lip_pucker_score

    def _calculate_distance_between_expression_pts(self, results_by_expression, expressions, left_pt, right_pt, distance_type='euclidian'):
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
                            get_px_pts_from_detection_result(
                                [left_pt] if side == 'left' else [right_pt],
                                mp.Image.create_from_file(data.get('file_path')),
                                data.get('result')
                            )[0].values()
                        ))
                   )
            points_by_expression.append(aux)

        for expressions_coords in points_by_expression:
            results.append(self._calculate_distance_pixels(expressions_coords[0], expressions_coords[1], distance_type))

        return results

    def _calculate_distance_from_expression_pts(self, results_by_expression, expressions, left_pts, right_pts, distance_type='euclidian'):
        if len(expressions) != 1:
            raise ValueError("Deve haver exatamente uma expressão para comparar.")

        results = []
        filtered_items = [item for item in results_by_expression if any(key in expressions for key in item)]

        for side in ['left', 'right']:
            for item in filtered_items:
                for expression, data in item.items():
                    expression_data = get_px_pts_from_detection_result(
                                left_pts if side == 'left' else right_pts,
                                mp.Image.create_from_file(data.get('file_path')),
                                data.get('result')
                            )
                    # print(expression, next(iter(expression_data[0].values())), next(iter(expression_data[1].values())))
                    distance = self._calculate_distance_pixels(next(iter(expression_data[0].values())), next(iter(expression_data[1].values())), distance_type)
                    results.append(distance)

        return results

    def _calculate_distance_mouth_variation(self, results_by_expression, expressions, left_pt, right_pt, reference_pt):
        if len(expressions) != 1:
            raise ValueError("Deve haver exatamente uma expressão para comparar.")

        filtered_items = [
            item for item in results_by_expression
            if any(key in expressions for key in item)
        ]

        def get_point_coordinates(point, item):
            expression_data = next(iter(get_px_pts_from_detection_result(
                [point],
                mp.Image.create_from_file(item['file_path']),
                item['result']
            )[0].values()))
            return expression_data

        points = [
            get_point_coordinates(pt, list(item.values())[0])
            for pt in [left_pt, right_pt, reference_pt]
            for item in filtered_items
        ]

        paralyzed_pt = points[0 if self.paralyzed_side == 'left' else 1]
        normal_pt = points[1 if self.paralyzed_side == 'left' else 0]
        ref_pt = points[2]

        normal_distance = self._calculate_distance_pixels(normal_pt, ref_pt)
        paralyzed_distance = self._calculate_distance_pixels(paralyzed_pt, ref_pt)

        return [normal_distance, paralyzed_distance]

    def _calculate_higher_variation_point(self, results_by_expression, expressions, left_pts, right_pts):
        if len(expressions) != 2:
            raise ValueError("Deve haver exatamente duas expressões para comparar.")

        results = {}

        for side in ['left', 'right']:
            points_by_expression = [
                {
                    expression: get_px_pts_from_detection_result(
                        left_pts if side == 'left' else right_pts,
                        mp.Image.create_from_file(data.get('file_path')),
                        data.get('result')
                    )
                    for expression, data in item.items()
                }
                for item in [item for item in results_by_expression if any(key in expressions for key in item)]
            ]

            try:
                expression_1_points = next(iter(points_by_expression[0].values()))
                expression_2_points = next(iter(points_by_expression[1].values()))
            except (IndexError, KeyError) as e:
                raise ValueError(f"Dados insuficientes para {expressions}") from e

            max_point, max_distance = None, 0
            for points_1, points_2 in zip(expression_1_points, expression_2_points):
                (key1, coord1), (key2, coord2) = list(points_1.items())[0], list(points_2.items())[0]

                if key1 == key2:
                    distance = self._calculate_distance_pixels(coord1, coord2, 'horizontal')
                    if distance > max_distance:
                        max_distance = distance
                        max_point = key1

            results[side] = {'max_point': max_point, 'max_distance': max_distance}

        return results

    def lowest_or_highest_coord(self, data: List[Dict[int, Tuple[int, int]]], axis: str, type: Literal["highest", "lowest"]) -> Tuple[int, int]:
        if axis not in ('x', 'y'):
            raise ValueError("O parâmetro 'eixo' deve ser 'x' ou 'y'")

        idx = 0 if axis == 'x' else 1
        if type == 'highest':
            return max((coord for item in data for coord in item.values()), key=lambda c: c[idx])
        return min((coord for item in data for coord in item.values()), key=lambda c: c[idx])

    def _calculate_highest_and_lowest_eyebrow_point(self, results_by_expression, expression, left_pts, right_pts):
        results_highest = []
        results_lowest = []
        filtered_items = [item for item in results_by_expression if any(key in [expression] for key in item)]

        for side in ['left', 'right']:
            for item in filtered_items:
                for expression, data in item.items():
                    # print('->', self.lowest_or_highest_coord(self.get_px_pts_from_detection_result(
                    #     left_pts if side == 'left' else right_pts,
                    #     mp.Image.create_from_file(data.get('file_path')),
                    #     data.get('result')
                    # ), 'x', 'lowest'))
                    results_highest.append(self.lowest_or_highest_coord(get_px_pts_from_detection_result(
                        left_pts if side == 'left' else right_pts,
                        mp.Image.create_from_file(data.get('file_path')),
                        data.get('result')
                    ), 'x', 'lowest'))
                    results_lowest.append(self.lowest_or_highest_coord(get_px_pts_from_detection_result(
                        left_pts if side == 'left' else right_pts,
                        mp.Image.create_from_file(data.get('file_path')),
                        data.get('result')
                    ), 'x', 'highest'))

        self.paralyzed_side = 'left' if results_highest[0][0] > results_highest[1][0] else 'right'

        return results_highest, results_lowest

    # exp2 qd existir deve ser 'Repouso'
    def _calculate_SB_forehead_wrinkle_score(self, results_by_expression, expression1, expression2=None, teste=''):
        if teste: print('-------------------------', expression1, expression2)
        if expression2:
            eyebrows_mid_pts_expression1 = self._get_eyebrow_mid_pt(results_by_expression, expression1)  # rest
            eyebrows_mid_pts_expression2 = self._get_eyebrow_mid_pt(results_by_expression, expression2)  # eyes closing
            forehead_mid_pt1 = self._get_px_pts_by_expression(results_by_expression, expression1, [self.mid_forhead_pt])[0]
            forehead_mid_pt2 = self._get_px_pts_by_expression(results_by_expression, expression2, [self.mid_forhead_pt])[0]
            # print('1a', eyebrows_mid_pts_expression1)
            # print('1b', eyebrows_mid_pts_expression2)
            # print('self.paralyzed_side', self.paralyzed_side)
            # print('forehead_mid_pt1', forehead_mid_pt1)
            # print('forehead_mid_pt2', forehead_mid_pt2)
            paralyzed_pt = eyebrows_mid_pts_expression1[0] if self.paralyzed_side == 'left' else eyebrows_mid_pts_expression1[1]
            normal_pt = eyebrows_mid_pts_expression2[0] if self.paralyzed_side == 'left' else eyebrows_mid_pts_expression2[1]
            normal_side_distance = self._calculate_distance_pixels(normal_pt, forehead_mid_pt2, 'horizontal')
            paralyzed_side_distance = self._calculate_distance_pixels(paralyzed_pt, forehead_mid_pt1, 'horizontal')
        else:
            eyebrows_mid_pts_expression1 = self._get_eyebrow_mid_pt(results_by_expression, expression1)
            # print('2a eyebrows_mid_pts_expression1', eyebrows_mid_pts_expression1)
            # print('self.paralyzed_side', self.paralyzed_side)
            paralyzed_pt = eyebrows_mid_pts_expression1[0] if self.paralyzed_side == 'left' else eyebrows_mid_pts_expression1[1]
            normal_pt = eyebrows_mid_pts_expression1[1] if self.paralyzed_side == 'left' else eyebrows_mid_pts_expression1[0]
            forehead_mid_pt = self._get_px_pts_by_expression(results_by_expression, expression1, [self.mid_forhead_pt])[0]
            normal_side_distance = self._calculate_distance_pixels(normal_pt, forehead_mid_pt, 'horizontal')
            paralyzed_side_distance = self._calculate_distance_pixels(paralyzed_pt, forehead_mid_pt, 'horizontal')
            # print('forehead_mid_pt', forehead_mid_pt)

        # print('normal_pt', normal_pt)
        # print('paralyzed_pt', paralyzed_pt)
        # print('normal_side_distance', normal_side_distance)
        # print('paralyzed_side_distance', paralyzed_side_distance)
        # perc_variation = (abs(normal_pt - paralyzed_pt) / normal_pt) * 100
        perc_variation = (abs(max(normal_side_distance, paralyzed_side_distance) - min(normal_side_distance, paralyzed_side_distance)) / max(normal_side_distance, paralyzed_side_distance)) * 100
        # print('forehead_wrinkle perc_variation', perc_variation)
        return self.calculate_SB_movement_percentage_score(perc_variation), perc_variation

    # exp2 qd existir deve ser 'Repouso'
    def _calculate_SB_gentle_eye_closure_score(self, results_by_expression, expression1, expression2=None, teste=''):
        if teste: print('-------------------------', expression1, expression2)
        distances_eyes_expression1 = self._calculate_distance_from_expression_pts(
            results_by_expression,
            [expression1],
            self.left_eye_open_pts,
            self.right_eye_open_pts,
            'horizontal'
        )
        # print('distances_eyes_expression1', distances_eyes_expression1)

        paralyzed_side_distance_eyes = distances_eyes_expression1[0 if self.paralyzed_side == 'left' else 1]
        normal_side_distance_eyes = distances_eyes_expression1[1 if self.paralyzed_side == 'left' else 0]

        if expression2:
            distances_eyes_expression2 = self._calculate_distance_from_expression_pts(
                results_by_expression,
                [expression2],
                self.left_eye_open_pts,
                self.right_eye_open_pts,
                'horizontal'
            )
            # print('distances_eyes_expression2', distances_eyes_expression2)
            normal_side_distance_eyes = distances_eyes_expression2[0 if self.paralyzed_side == 'left' else 1]

        # perc_variation_eyes = abs(normal_side_distance_eyes - paralyzed_side_distance_eyes) / normal_side_distance_eyes * 100
        perc_variation_eyes = (abs(max(normal_side_distance_eyes, paralyzed_side_distance_eyes) - min(normal_side_distance_eyes, paralyzed_side_distance_eyes)) / max(normal_side_distance_eyes, paralyzed_side_distance_eyes)) * 100

        # print('paralyzed_side_distance_eyes', paralyzed_side_distance_eyes)
        # print('normal_side_distance_eyes', normal_side_distance_eyes)
        # print('perc_variation_eyes perc_variation', perc_variation_eyes)
        return self.calculate_SB_movement_percentage_score(perc_variation_eyes), perc_variation_eyes

    def _calculate_SB_open_mouth_smile_score(self, results_by_expression, expression, teste=''):
        if teste: print('-------------------------', expression)
        distances_mouth = self._calculate_distance_between_expression_pts(
            results_by_expression,
            ['Repouso', expression],
            self.left_mouth_end_pt,
            self.right_mouth_end_pt,
            'vertical'
        )
        paralyzed_side_distance_mouth = distances_mouth[0 if self.paralyzed_side == 'left' else 1]
        normal_side_distance_mouth = distances_mouth[1 if self.paralyzed_side == 'left' else 0]
        # perc_variation = abs(
        #     normal_side_distance_mouth - paralyzed_side_distance_mouth) / normal_side_distance_mouth * 100
        perc_variation = (abs(max(normal_side_distance_mouth, paralyzed_side_distance_mouth) - min(
            normal_side_distance_mouth, paralyzed_side_distance_mouth)) / max(normal_side_distance_mouth,
                                                                            paralyzed_side_distance_mouth)) * 100
        # print('distances_mouth', distances_mouth)
        # print('mouth_smile perc_variation', perc_variation)
        # print('-------------------------')
        return self.calculate_SB_movement_percentage_score(perc_variation), perc_variation

    def _calculate_SB_snarl_score(self, results_by_expression, teste=''):
        if teste: print('-------------------------', teste)
        distances = self._calculate_distance_between_expression_pts(
            results_by_expression,
            ['Repouso', 'Elevar o lábio superior'],
            self.alar_base_pts[1],
            self.alar_base_pts[0],
            'vertical'
        )
        paralyzed_side_distance = distances[0 if self.paralyzed_side == 'left' else 1]
        normal_side_distance = distances[1 if self.paralyzed_side == 'left' else 0]
        # print('distances', distances)
        # print('paralyzed_side_distance', paralyzed_side_distance)
        # print('normal_side_distance', normal_side_distance)

        perc_variation = (abs(max(normal_side_distance, paralyzed_side_distance) - min(
            normal_side_distance, paralyzed_side_distance)) / max(normal_side_distance,
                                                                            paralyzed_side_distance)) * 100
        # print('snarl perc_variation', perc_variation)

        return self.calculate_SB_movement_percentage_score(perc_variation)

    def _calculate_SB_lip_pucker_score(self, results_by_expression, teste=''):
        if teste: print('-------------------------', teste)
        distances_rest = self._calculate_distance_from_expression_pts(
            results_by_expression,
            ['Repouso'],
            self.left_mouth_lip_p_pts,
            self.right_mouth_lip_p_pts,
        )
        # print('distances_rest', distances_rest)

        distances_lip_pucker = self._calculate_distance_from_expression_pts(
            results_by_expression,
            ['Assobiar'],
            self.left_mouth_lip_p_pts,
            self.right_mouth_lip_p_pts,
        )
        # print('distances_lip_pucker', distances_lip_pucker)

        excursion_left = abs(distances_rest[0] - distances_lip_pucker[0])
        excursion_right = abs(distances_rest[1] - distances_lip_pucker[1])
        # print('excursion_left', excursion_left)
        # print('excursion_right', excursion_right)

        paralyzed_side_distance = excursion_left if self.paralyzed_side == 'left' else excursion_right
        normal_side_distance = excursion_right if self.paralyzed_side == 'left' else excursion_left
        # print('paralyzed_side_distance', paralyzed_side_distance)
        # print('normal_side_distance', normal_side_distance)

        # perc_variation = abs(
        #     normal_side_distance - paralyzed_side_distance) / normal_side_distance * 100
        perc_variation = (abs(max(normal_side_distance, paralyzed_side_distance) - min(
            normal_side_distance, paralyzed_side_distance)) / max(normal_side_distance,
                                                                            paralyzed_side_distance)) * 100
        # print('lip_pucker perc_variation', perc_variation)

        return self.calculate_SB_movement_percentage_score(perc_variation)

    def _calculate_mid_point(self, pts):
        total_pts = len(pts)
        sum_x = 0
        sum_y = 0

        for pt in pts:
            _, (x, y) = next(iter(pt.items()))
            sum_x += x
            sum_y += y

        return (int(sum_x / total_pts), int(sum_y / total_pts))

    def _get_eyebrow_mid_pt(self, results_by_expression, exp):
        results = []
        right_eyebrow_pts = self.right_eyebrow_pts[:5]
        left_eyebrow_pts = self.left_eyebrow_pts[:5]
        filtered_items = [item for item in results_by_expression if any(key in exp for key in item)]

        for side in ['left', 'right']:
            for item in filtered_items:
                for expression, data in item.items():
                    expression_data = get_px_pts_from_detection_result(
                                left_eyebrow_pts if side == 'left' else right_eyebrow_pts,
                                mp.Image.create_from_file(data.get('file_path')),
                                data.get('result')
                            )
                    results.append(self._calculate_mid_point(expression_data))
        return results

    def _get_px_pts_by_expression(self, results_by_expression, exp, pts):
        results = []
        filtered_items = [item for item in results_by_expression if any(key in exp for key in item)]

        for item in filtered_items:
            for expression, data in item.items():
                expression_data = get_px_pts_from_detection_result(
                            pts,
                            mp.Image.create_from_file(data.get('file_path')),
                            data.get('result')
                        )
                results.append(next(iter(expression_data[0].values())))
        return results

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

    def file_to_base64(self, file_path, compression_level=None):
        try:
            if compression_level is not None:
                with Image.open(file_path) as img:
                    output = io.BytesIO()
                    img.save(output, format=img.format, quality=compression_level)
                    output.seek(0)
                    return base64.b64encode(output.read()).decode("utf-8")
            else:
                with open(file_path, "rb") as file:
                    return base64.b64encode(file.read()).decode("utf-8")
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Erro: {e}")
            return None