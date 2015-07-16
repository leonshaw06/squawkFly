#!/usr/local/bin/python

import cv2
import cv2.cv as cv
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import structureTools as struc

plt.style.use('ggplot')


def main():
    data_3d = [[0, 0, 0],
               [10, 10, 10],
               [20, 20, 20],
               [30, 30, 30],
               [40, 40, 40],
               [50, 50, 50],
               [60, 40, 40],
               [70, 30, 30],
               [80, 20, 20],
               [90, 10, 10],
               [100, 0, 0]]

    data_3d = np.array(data_3d, dtype='float32')

    # artificial camera with f=5 units, cx = cy = 5 units
    K = struc.CalibArray(5, 5, 5)
    distCoeffs = (0, 0, 0, 0)

    # projections into image planes with the camera in different poses
    tvec = (0, 0, 30)
    rvec = (0, 0, 0)
    img_pts1, jacobian = cv2.projectPoints(
        data_3d, rvec, tvec, K, distCoeffs)

    tvec = (0, 15, 40)
    rvec = (0, 0.2, 0)
    img_pts2, jacobian = cv2.projectPoints(
        data_3d, rvec, tvec, K, distCoeffs)

    plotSimulation(data_3d)

    print img_pts1
    plotImagePoints(img_pts1)

    print img_pts2
    plotImagePoints(img_pts2)


# Plotting of the system in 3d
def plotSimulation(objectPoints):

    all_x = [row[0] for row in objectPoints]
    all_y = [row[1] for row in objectPoints]
    all_z = [row[2] for row in objectPoints]

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    ax.scatter(all_x, all_y, all_z, zdir='z')

    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    # ax.set_xlim(0, 100)
    # ax.set_ylim(0, 100)
    # ax.set_zlim(0, 100)

    plt.show()


def plotImagePoints(imagePoints):

    all_x = [point[0][0] for point in imagePoints]
    all_y = [point[0][1] for point in imagePoints]

    plt.scatter(all_x, all_y)
    plt.scatter(all_x[0], all_y[0], color='r')
    plt.show()

main()
