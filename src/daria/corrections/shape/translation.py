from typing import Optional

import cv2
import matplotlib.pyplot as plt
import numpy as np

from daria.utils.features import FeatureDetection


class TranslationEstimator:
    """
    Class for computing translations to align images based on feature detection.
    """

    def __init__(self, max_features: int = 200, tol: float = 0.05):
        """
        Setup of user-defined tuning parameters.

        Args:
            max_features (int): feature detection parameter
            tol (float): tolerance used to detect whether matching transformation is a
                translation
        """
        self._max_features = max_features
        self._tol = tol

    def find_effective_translation(
        self,
        img_src: np.ndarray,
        img_dst: np.ndarray,
        roi_src: Optional[tuple],
        roi_dst: Optional[tuple],
        plot_matches: bool = False,
    ) -> tuple:
        """
        Find effective translation to align to images, such that when restricted to an ROI,
        both images have matching features.

        Args:
            img_src (np.ndarray): source image
            img_dst (np.ndarray): destination image
            roi_src (tuple of slices): region of interested associated to the source image
            roi_dst (tuple of slices): region of interested associated to the destination image
            plot_matches (bool): flag controlling whether the matching features are plotted;
                useful for debugging; default value is False

        Returns:
            np.ndarray: aligned source image
            bool: flag indicating whether the procedure was successful
        """
        # Make several attempts to find a matching transformation.
        # First attempt to match both images, using a homography.
        # Finding a homography is the preferred approach, as it
        # allows for slightly more robustness control as transformation
        # models with less DOFs; a homography has 8 DOFs. Robustness is
        # later checked by comparing the linear contribution with the
        # identity matrix.
        # If the first attempt was not successful, try a second attempt.
        # Here, not a homography will be set up, but a similarity transform, i.e.,
        # an affine map describing scaling, rotation, and translation. This boils
        # down to 4 DOFs. Thus, the robustness comparison is easier to trick
        # compared to the first case.
        for transformation_type in ["homography", "partial_affine"]:
            transformation, _, matches = self._find_matching_transformation(
                img_src,
                img_dst,
                roi_src,
                roi_dst,
                transformation_type=transformation_type,
                return_matches=True,
                plot_matches=plot_matches,
            )

            # Check whether the transformation is close to a translation and extract the
            # effective translation (as affine map) as average translation between the
            # matches.
            if self._isclose_translation(transformation):
                (
                    translation,
                    intact_translation,
                ) = self._find_translation(matches)
            else:
                translation = None
                intact_translation = False

            # Accept resulting transformation if it can be casted as translation
            if intact_translation:
                break

        return translation, intact_translation

    def match_roi(
        self,
        img_src: np.ndarray,
        img_dst: np.ndarray,
        roi_src: Optional[tuple],
        roi_dst: Optional[tuple],
        plot_matches: bool = False,
    ) -> np.ndarray:
        """
        Align two images, such that when restricted to an ROI, both images have matching
        features.

        Args:
            img_src (np.ndarray): source image
            img_dst (np.ndarray): destination image
            roi_src (tuple of slices): region of interested associated to the source image
            roi_dst (tuple of slices): region of interested associated to the destination image
                translation
            plot_matches (bool): flag controlling whether the matching features are plotted;
                useful for debugging; default value is False

        Returns:
            np.ndarray: aligned source image
        """
        # Determine effective translation
        translation, intact_translation = self.find_effective_translation(
            img_src, img_dst, roi_src, roi_dst, plot_matches
        )

        if not intact_translation:
            raise ValueError("ROIs cannot be aligned by translation.")

        # Apply translation
        (h, w) = img_dst.shape[:2]
        aligned_img_src = cv2.warpAffine(img_src, translation, (w, h))

        return aligned_img_src

    def _find_matching_transformation(
        self,
        img_src: np.ndarray,
        img_dst: np.ndarray,
        roi_src: Optional[tuple] = None,
        roi_dst: Optional[tuple] = None,
        transformation_type: str = "homography",
        keep_percent: float = 0.1,
        return_matches: bool = False,
        plot_matches: bool = False,
    ) -> tuple:
        """
        Determine matching transformation (homography or partial affine transformation),
        matching two given, possibly ROI-restricted, images.

        Args:
            img_src (np.ndarray): source image
            img_dst (np.ndarry): destination image
            roi_src (tuple of slices, optional): region of interest for the source image
            roi_dst (tuple of slices, optional): region of interest for the destination image
            transformation_type (str): either "homography" or "partial_affine"
            keep_percent (float): how much of the features should be considered for finding
                the transformation
            return_matches (bool): flag controlling whether the inliers among all matches
                are returned
            plot_matches (bool): flag controlling whether found matches are plotted;
                default is False

        Returns:
            np.ndarray: transformation matrix
            bool: flag indicating whether the procedure was successful
        """
        if transformation_type not in ["homography", "partial_affine"]:
            raise ValueError(
                f"Transformation type {transformation_type} not supported."
            )

        # Manage ROIs
        if roi_src is not None:
            if roi_dst is None:
                roi_dst = roi_src

            # Only cover the case of compatible ROIs for now.
            assert img_src[roi_src].shape == img_dst[roi_dst].shape

        # Extract features for both images restricted to the ROI containing the color palette
        features_src, have_features_src = FeatureDetection.extract_features(
            img_src, roi_src, self._max_features
        )
        features_dst, have_features_dst = FeatureDetection.extract_features(
            img_dst, roi_dst
        )

        # Check whether features are valid
        if not (have_features_src and have_features_dst):
            if return_matches:
                return None, False, None
            else:
                return None, False

        # Determine matching points
        (pts_src, pts_dst), have_match, matches = FeatureDetection.match_features(
            features_src,
            features_dst,
            keep_percent=keep_percent,
            return_matches=True,
        )

        # Determine matching transformation. Allow for different models.
        transformation = None
        if have_match:
            # Homography
            if transformation_type == "homography":
                transformation, mask = cv2.findHomography(
                    pts_src, pts_dst, method=cv2.RANSAC
                )
            # Affine map including merely scaling, rotation, and translation
            elif transformation_type == "partial_affine":
                transformation, mask = cv2.estimateAffinePartial2D(pts_src, pts_dst)

        # Monitor success
        intact_transformation = transformation is not None

        # Flag inliers
        inliers = (
            (
                pts_src[mask[:, 0].astype(bool)].reshape(-1, 2),
                pts_dst[mask[:, 0].astype(bool)].reshape(-1, 2),
            )
            if intact_transformation
            else None
        )

        # Plot matches in both images
        if plot_matches and intact_transformation:
            kps_src, _ = features_src
            kps_dst, _ = features_dst

            matchedVis = cv2.drawMatches(
                img_src, kps_src, img_dst, kps_dst, matches, None
            )

            plt.imshow(matchedVis)
            plt.show()

        if return_matches:
            return transformation, intact_transformation, inliers
        else:
            return transformation, intact_transformation

    def _isclose_translation(self, transformation: np.ndarray) -> bool:
        """
        Checking whether a transformation is close to a translation.

        Args:
            transformation (np.ndarray): transformation matrix, e.g., homography,
                or affine map

        Returns:
            bool: flag whether transformation is close to a translation
        """
        return (
            transformation is not None
            and np.isclose(transformation[:2, :2], np.eye(2), atol=self._tol).all()
        )

    def _find_translation(self, matches: tuple) -> tuple:
        """
        Determine a translation as average translation between two sets of points.

        NOTE: The average translation is identical to the least squares minimizer
        among all translations. Including RANSAC would be optimal. However, in
        all workflows this method will be combined with methods like
        find_matching_transformation which involve RANSAC.

        Args:
            matches (tuple of arrays): src and dst points, which are supposed to
                be a translation from each other apart.
        Returns:
            np.ndarray: translation matrix
            bool: flag indicating whether the procedure was successful
        """
        # Extract the translation directly as average displacement from all
        # provided matches - have to assume that the matches are well chosen.
        src, dst = matches
        displacement = np.average(dst - src, axis=0)
        affine_translation = np.hstack((np.eye(2), displacement.reshape((2, 1))))

        # Procedure successful - return the translation
        return affine_translation, True
