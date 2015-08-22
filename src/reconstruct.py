#!/usr/local/bin/python

import sys
import cv2
import cv2.cv as cv
import numpy as np
import math
import matplotlib.pyplot as plt
from collections import namedtuple
from mpl_toolkits.mplot3d import Axes3D
import os.path
import numpy.random as random

import fundamental as fund
import triangulation as tri
import structureTools as tools
import plotting as plot

random.seed()
np.set_printoptions(suppress=True)
# plt.style.use('ggplot')

Point = namedtuple("Point", "x y")

view = True
simulation = False


def synchroniseAtApex(pts_1, pts_2):
    print "APEX SYNCHRONISATION"

    syncd1 = []
    syncd2 = []
    shorter = []
    longer = []
    short_flag = 0

    if len(pts_1) < len(pts_2):
        shorter = pts_1
        longer = pts_2
        short_flag = 1
    else:
        shorter = pts_2
        longer = pts_1
        short_flag = 2

    diff = len(longer) - len(shorter)
    print "Difference in lengths:", diff
    # find the highest y value in each point set
    apex1 = max(float(p[1]) for p in shorter)
    apex2 = max(float(p[1]) for p in longer)

    apex1_i = [i for i, y in enumerate(shorter) if y[1] == apex1]
    apex2_i = [i for i, y in enumerate(longer) if y[1] == apex2]

    print "\nAPEXES"
    print "Short:", apex1, apex1_i, "of", len(shorter)
    print "Long:", apex2, apex2_i, "of", len(longer)

    shift = apex2_i[0] - apex1_i[0]

    # remove the front end dangle
    print "\nShift by:", shift

    if shift > 0:
        longer = longer[shift:]
        print "Longer front trimmed, new length:", len(longer)
    else:
        shorter = shorter[abs(shift):]
        print "Shorter front trimmed, new length:", len(shorter)

    remainder = diff - shift

    # remove the rear end dangle
    if remainder >= 0:
        print "\nTrim longer by remainder:", remainder
        index = len(longer) - remainder
        print "Trim to index:", index
        longer = longer[:index]

    if remainder < 0:
        index = len(shorter) - abs(remainder)
        print "\nShift > diff in lengths, trim the shorter end to:", index
        shorter = shorter[:index]

    print "New length of shorter:", len(shorter)
    print "New length of longer:", len(longer)

    # find the highest y value in each point set
    apex1 = max(float(p[1]) for p in shorter)
    apex2 = max(float(p[1]) for p in longer)

    apex1_i = [i for i, y in enumerate(shorter) if y[1] == apex1]
    apex2_i = [i for i, y in enumerate(longer) if y[1] == apex2]

    print "\nNew apex positions:"
    print apex1, apex1_i
    print apex2, apex2_i

    if short_flag == 1:
        syncd1 = shorter
        syncd2 = longer
    else:
        syncd1 = longer
        syncd2 = shorter

    if view:
        plot.plot2D(syncd1, name='First Synced Trajectory')
        plot.plot2D(syncd2, name='Second Synced Trajectory')

    return syncd1, syncd2


# add some random noise to n image point set
def addNoise(scale, points):
    new = []
    mags = []
    for p in points:

        nx = random.normal(0, scale)
        ny = random.normal(0, scale)

        print "Add noise:", nx, ny
        n0 = p[0] + nx
        n1 = p[1] + ny
        n = [n0, n1]
        new.append(n)
        mags.append(abs(nx))
        mags.append(abs(ny))

    avg_mag = sum(mags) / len(mags)

    return np.array(new, dtype='float32'), avg_mag


# Get point correspondeces (1+2) from subdir
# Optionally: original 3d set, correspondences to be reconstructed (3+4)
def getData(folder):
    path = 'tests/' + str(folder) + '/'
    pts1 = []
    pts2 = []
    pts3 = []
    pts4 = []
    postPts1 = []
    postPts2 = []
    data3D = []

    with open(path + 'pts1.txt') as datafile:
        data = datafile.read()
        datafile.close()

    data = data.split('\n')
    for row in data:
        x = float(row.split()[0])
        y = float(row.split()[1])
        pts1.append([x, y])

    with open(path + 'pts2.txt') as datafile:
        data = datafile.read()
        datafile.close()

    data = data.split('\n')
    for row in data:
        x = float(row.split()[0])
        y = float(row.split()[1])
        pts2.append([x, y])

    try:
        with open(path + '3d.txt') as datafile:
            data = datafile.read()
            datafile.close()

        data = data.split('\n')
        for row in data:
            x = float(row.split()[0])
            y = float(row.split()[1])
            z = float(row.split()[2])
            data3D.append([x, y, z])

        print "> 3D reference data provided. Simulation."

    except IOError:
        print "> No 3D reference data provided. Not a simulation."

    try:
        with open(path + 'pts3.txt') as datafile:
            data = datafile.read()
            datafile.close()

        data = data.split('\n')
        for row in data:
            x = float(row.split()[0])
            y = float(row.split()[1])
            pts3.append([x, y])

        with open(path + 'pts4.txt') as datafile:
            data = datafile.read()
            datafile.close()

        data = data.split('\n')
        for row in data:
            x = float(row.split()[0])
            y = float(row.split()[1])
            pts4.append([x, y])

        rec_data = True
        print "> Designated reconstruction correspondences provided."

    except IOError:
        print "> No reconstruction points provided. Using full point set."
        pts3 = pts1
        pts4 = pts2
        rec_data = False

    try:
        with open(path + 'postPts1.txt') as datafile:
            data = datafile.read()
            datafile.close()
        data = data.split('\n')
        for row in data:
            x = float(row.split()[0])
            y = float(row.split()[1])
            postPts1.append([x, y])
    except IOError:
        pass

    try:
        with open(path + 'postPts2.txt') as datafile:
            data = datafile.read()
            datafile.close()
        data = data.split('\n')
        for row in data:
            x = float(row.split()[0])
            y = float(row.split()[1])
            postPts2.append([x, y])
    except IOError:
        pass

    return data3D, pts1, pts2, pts3, pts4, postPts1, postPts2, rec_data


def undistortData(points, K, d):

    points = np.array(points, dtype='float32').reshape((-1, 1, 2))
    points = cv2.undistortPoints(
        src=points, cameraMatrix=K, distCoeffs=d, P=K).tolist()

    points_ = []
    for p in points:
        points_.append(p[0])

    return points_


def run():
    global pts3
    global pts4

    if simulation and view:
        plot.plot3D(data3D, 'Original 3D Data')

    if view:
        plot.plot2D(pts1_raw, name='First Statics (Noise not shown)')
        plot.plot2D(pts2_raw, name='Second Statics (Noise not shown)')

    # FUNDAMENTAL MATRIX
    F = getFundamentalMatrix(pts1, pts2)

    # ESSENTIAL MATRIX (HZ 9.12)
    E, w, u, vt = getEssentialMatrix(F, K1, K2)

    # PROJECTION/CAMERA MATRICES from E (HZ 9.6.2)
    P1, P2 = getNormalisedPMatrices(u, vt)
    P1_mat = np.mat(P1)
    P2_mat = np.mat(P2)

    # FULL PROJECTION MATRICES (with K) P = K[Rt]
    KP1 = K1 * P1_mat
    KP2 = K2 * P2_mat

    print "\n> KP1:\n", KP1
    print "\n> KP2:\n", KP2

    # SYNCHRONISATION + CORRECTION
    if rec_data and simulation is False:
        pts3, pts4 = synchroniseAtApex(pts3, pts4)
        # pts3, pts4 = synchroniseGeometric(pts3, pts4, F)

        pts3 = pts3.reshape((1, -1, 2))
        pts4 = pts4.reshape((1, -1, 2))
        newPoints3, newPoints4 = cv2.correctMatches(F, pts3, pts4)
        pts3 = newPoints3.reshape((-1, 2))
        pts4 = newPoints4.reshape((-1, 2))

    elif simulation:
        pts3 = pts1
        pts4 = pts2

    # Triangulate the trajectory
    p3d = triangulateCV(KP1, KP2, pts3, pts4)

    # Triangulate goalposts
    if simulation is False:
        goalPosts = triangulateCV(KP1, KP2, postPts1, postPts2)

    # SCALING AND PLOTTING
    if simulation:
        if view:
            plot.plot3D(p3d, 'Simulation Reconstruction')
        reprojectionError(K1, P1_mat, K2, P2_mat, pts3, pts4, p3d)
        p3d = simScale(p3d)
        if view:
            plot.plot3D(p3d, 'Scaled Simulation Reconstruction')

    else:
        # add the post point data into the reconstruction for context
        if len(postPts1) == 4:
            pts3_gp = np.concatenate((postPts1, pts3), axis=0)
            pts4_gp = np.concatenate((postPts2, pts4), axis=0)
            p3d_gp = np.concatenate((goalPosts, p3d), axis=0)

        scale = getScale(goalPosts)

        scaled_gp_only = [[a * scale for a in inner] for inner in goalPosts]
        scaled_gp = [[a * scale for a in inner] for inner in p3d_gp]
        scaled = [[a * scale for a in inner] for inner in p3d]

        if view:
            plot.plot3D(p3d_gp, 'Original (Unscaled) Reconstruction')
            plot.plot3D(scaled_gp_only, 'Scaled Goal Posts')
            plot.plot3D(scaled_gp, 'Scaled 3D Reconstruction')
        reprojectionError(K1, P1_mat, K2, P2_mat, pts3_gp, pts4_gp, p3d_gp)

        getMetrics(scaled, scaled_gp_only)

        scaled_gp = transform(scaled_gp)
        if view:
            plot.plot3D(scaled_gp, 'Scaled and Reorientated 3D Reconstruction')
        if simulation:
            reconstructionError(data3D, scaled_gp)

        # write X Y Z to file
        outfile = open('tests/' + folder + '/3d_out.txt', 'w')
        for p in scaled_gp:
            p0 = round(p[0], 2)
            p1 = round(p[1], 2)
            p2 = round(p[2], 2)
            string = str(p0) + ' ' + str(p1) + ' ' + str(p2)
            outfile.write(string + '\n')
        outfile.close()


# the error simulation is a sphere of unit radius
def simScale(points):
    cx = 0
    cy = 0
    cz = 0
    d = 0

    print "---Sim Scale---"

    for p in points:
        cx += p[0]
        cy += p[1]
        cz += p[2]

    # centroid of shape
    cx = cx / len(points)
    cy = cy / len(points)
    cz = cz / len(points)

    print "> Centroid:", cx, cy, cz

    # translate the whole thing to the origin
    d = 0
    translated = []
    for p in points:
        nx = p[0] - cx
        ny = p[1] - cy
        nz = p[2] - cz
        translated.append((nx, ny, nz))

        nd = ((nx ** 2) + (ny ** 2) + (nz ** 2)) ** 0.5
        d += nd

    # average distance to origin
    d = d / len(points)
    scale = 1 / d

    print "> Average distance to origin:", d
    print "> Scale by:", scale

    scaled = []
    for p in translated:
        n = tuple([a * scale for a in p])
        scaled.append(n)

    distances = []
    for p in scaled:
        d = ((p[0] ** 2) + (p[1] ** 2) + (p[2] ** 2)) ** 0.5
        distances.append(d)

    avg = np.mean(distances)
    std = np.std(distances)

    outfile = open('tests/' + folder + statdir + 'reconstruction.txt', 'w')
    outfile.write('avg distance to origin: ' + str(avg) + '\n')
    outfile.write('std: ' + str(std) + '\n')
    outfile.write('distances:\n')

    offset = []
    for d in distances:
        offset.append(abs(d - 1))
    if view:
        plot.plotOrderedBar(offset, name='Offset in Distance to Origin')
    for o in offset:
        outfile.write(str(o) + '\n')
    outfile.close()

    print "statfile:", std
    statfile.write(str(std) + '\n')

    return np.array(scaled, dtype='float32')


# transform the scaled 3d model so that it's orientation is sensible
def transform(points):

    # STEP ONE: translate everything so that the first ball point is at origin
    translated = []
    anchor = points[4]

    x0 = anchor[0]
    y0 = anchor[1]
    z0 = anchor[2]

    print "\n---Translate Trajectory Anchor to Origin---"
    for p in points:
        x = p[0] - x0
        y = p[1] - y0
        z = p[2] - z0
        translated.append((x, y, z))

    print "new trajectory anchor:\n", translated[4]

    # STEP TWO: Rotate everything so that bottom-left GP lies on z-axis.
    # Eliminate y component by rotating around x:
    print "\n---Eliminate Y from Bottom left---"
    bl = translated[0]
    x = bl[0]
    y = bl[1]
    z = bl[2]
    L = ((y ** 2) + (z ** 2)) ** 0.5

    theta = math.asin(y / L)
    cos = math.cos(theta)
    sin = math.sin(theta)

    print "rotate by theta around x:", theta
    rotated_x = []
    rotx = np.mat([[1, 0, 0],
                   [0, cos, -sin],
                   [0, sin, cos]], dtype='float32')

    for p in translated:
        p = np.mat(p)
        n = rotx * p.T
        rotated_x.append((n[0, 0], n[1, 0], n[2, 0]))

    print "new bottom left:\n", rotated_x[0]

    # eliminate x component by rotating round y
    print "\n---Eliminate X from Bottom Left---"
    bl = rotated_x[0]
    x = bl[0]
    y = bl[1]
    z = bl[2]
    L = ((x ** 2) + (z ** 2)) ** 0.5

    theta = -1 * math.asin(x / L)
    cos = math.cos(theta)
    sin = math.sin(theta)

    print "rotate by theta around y:", theta
    rotated_y = []
    roty = np.mat([[cos, 0, sin],
                   [0, 1, 0],
                   [-sin, 0, cos]], dtype='float32')

    for p in rotated_x:
        p = np.mat(p)
        n = roty * p.T
        rotated_y.append((n[0, 0], n[1, 0], n[2, 0]))

    print "new bottom left:\n", rotated_y[0]

    # rotate bottom right into Z-X plance (no Y)
    print "\n---Rotate Bottom into ZX Plane (Floor - No Y)---"
    br = rotated_y[3]
    x = br[0]
    y = br[1]
    z = br[2]
    L = ((x ** 2) + (y ** 2)) ** 0.5

    theta = -1 * math.asin(y / L)
    cos = math.cos(theta)
    sin = math.sin(theta)

    print "rotate by theta about y:", theta
    rotated_z = []
    rotz = np.mat([[cos, -sin, 0],
                   [sin, cos, 0],
                   [0, 0, 1]], dtype='float32')

    for p in rotated_y:
        p = np.mat(p)
        n = rotz * p.T
        rotated_z.append((n[0, 0], n[1, 0], n[2, 0]))

    print "new bottom right:\n", rotated_z[3]

    # temporary to bring it into alignment with the main simulation data
    if simulation:
        sim_offset = 10
    else:
        sim_offset = 0

    new = []
    for i in range(0, 4):
        p = rotated_z[i]
        new.append((p[0] + sim_offset, p[1] + sim_offset, p[2]))

    for i in range(4, len(rotated_z)):
        p = rotated_z[i]
        new.append((p[0] + sim_offset, p[1] + sim_offset, p[2]))

    return np.array(new, dtype='float32')


# given the scaled up set of trajectory points work out the speed and
# distance to goal
def getMetrics(worldPoints, goalPosts):
    outfile = open('tests/' + folder + '/speed.txt', 'w')
    first = worldPoints.pop(0)
    prev = first
    speeds = []
    for p in worldPoints:
        dist = sep3D(p, prev)

        # dist is m travelled in ~15ms
        speed = 58 * dist
        mph = 2.23693629 * speed
        outfile.write(str(speed) + ' ' + str(mph) + '\n')

        speeds.append(mph)

        prev = p

    outfile.close()

    # calculate range
    bottomLeft = goalPosts[0]
    bottomRight = goalPosts[3]
    middleOfGoal = midpoint(bottomLeft, bottomRight)
    shotRange = int(sep3D(first, middleOfGoal))

    avg = int(sum(speeds) / len(speeds))
    avgms = avg / 2.237
    time = round(float(shotRange) / float(avgms), 1)

    print "> Distance Covered:", str(shotRange) + 'm'
    print "> Average speed: ", str(avg) + 'mph'
    print "> Distance covered in:", str(time) + 's'

    outfile = open('tests/' + folder + '/tracer_stats.txt', 'w')
    outfile.write(str(avg) + '\n')
    outfile.write(str(shotRange))
    outfile.close()


def midpoint(a, b):
    x0 = a[0]
    y0 = a[1]
    z0 = a[2]

    x1 = b[0]
    y1 = b[1]
    z1 = b[2]

    x = (x0 + x1) / 2
    y = (y0 + y1) / 2
    z = (z0 + z1) / 2

    return (x, y, z)


# get the Fundamental matrix by the normalised eight point algorithm
def getFundamentalMatrix(pts_1, pts_2):

    # normalised 8-point algorithm
    F, mask = cv2.findFundamentalMat(pts_1, pts_2, cv.CV_FM_8POINT)
    tools.is_singular(F)

    # test on original coordinates
    print "\n> Fundamental:\n", F
    avg, std = fund.testFundamentalReln(F, pts_1, pts_2)

    outfile = open('tests/' + folder + statdir + 'epilines.txt', 'w')
    string = 'avg:' + str(avg) + ' std1:' + str(std)
    outfile.write(string)
    outfile.close()
    print "statfile:", avg, std
    statfile.write(str(avg) + ' ' + str(std) + ' ')

    return F


def getEssentialMatrix(F, K1, K2):

    E = K2.T * np.mat(F) * K1
    print "\n> Essential:\n", E

    fund.testEssentialReln(E, norm_pts1, norm_pts2)
    s, u, vt = cv2.SVDecomp(E)

    print "> SVDecomp(E):"
    print "u:\n", u
    print "vt:\n", vt
    print "\n> Singular values:\n", s
    return E, s, u, vt


# https://en.wikipedia.org/wiki/Eight-point_algorithm#Step_3:_Enforcing_the_internal_constraint
def getConstrainedEssentialMatrix(u, vt):
    diag = np.mat(np.diag([1, 1, 0]))

    E_prime = np.mat(u) * diag * np.mat(vt)
    print "\n> Constrained Essential = u * diag(1,1,0) * vt:\n", E_prime
    fund.testEssentialReln(E_prime, norm_pts1, norm_pts2)

    s2, u2, vt2 = cv2.SVDecomp(E_prime)
    print "\n> Singular values:\n", s2

    return E_prime, s2, u2, vt2


def getNormalisedPMatrices(u, vt):
    R1 = np.mat(u) * np.mat(W) * np.mat(vt)
    R2 = np.mat(u) * np.mat(W.T) * np.mat(vt)

    # negate R if det(R) negative
    if np.linalg.det(R1) < 0:
        R1 = -1 * R1

    if np.linalg.det(R2) < 0:
        R2 = -1 * R2

    t1 = u[:, 2]
    t2 = -1 * u[:, 2]

    R, t = getValidRtCombo(R1, R2, t1, t2)

    # NORMALISED CAMERA MATRICES P = [Rt]
    P1 = BoringCameraArray()  # I|0
    P2 = CameraArray(R, t)    # R|t

    print "\n> P1:\n", P1
    print "\n> P2:\n", P2

    return P1, P2


def getValidRtCombo(R1, R2, t1, t2):
    # enforce positive depth combination of Rt using normalised coords
    if testRtCombo(R1, t1, norm_pts1, norm_pts2):
        print "\n> R|t: R1 t1"
        R = R1
        t = t1

    elif testRtCombo(R1, t2, norm_pts1, norm_pts2):
        print "\n> R|t: R1 t2"
        R = R1
        t = t2

    elif testRtCombo(R2, t1, norm_pts1, norm_pts2):
        print "\n> R|t: R2 t1"
        R = R2
        t = t1

    elif testRtCombo(R2, t2, norm_pts1, norm_pts2):
        print "\n> R|t: R2 t2"
        R = R2
        t = t2

    else:
        print "ERROR: No positive depth Rt combination"
        sys.exit()

    print "R:\n", R
    print "t:\n", t
    return R, t


# which combination of R|t gives us a P pair that works geometrically
# ie: gives us a positive depth measure in both
def testRtCombo(R, t, norm_pts1, norm_pts2):
    P1 = BoringCameraArray()
    P2 = CameraArray(R, t)
    points3d = []

    for i in range(0, len(norm_pts1)):
        x1 = norm_pts1[i][0]
        y1 = norm_pts1[i][1]

        x2 = norm_pts2[i][0]
        y2 = norm_pts2[i][1]

        u1 = Point(x1, y1)
        u2 = Point(x2, y2)

        X = tri.LinearTriangulation(P1, u1, P2, u2)
        points3d.append(X[1])

    # check if any z coord is negative
    for point in points3d:
        if point[2] < -0.05:
            return False
    return True


# linear least squares triangulation for one 3-space point X
def triangulateLS(P1, P2, pts_1, pts_2):
    points3d = []

    for i in range(0, len(pts_1)):

        x1 = pts_1[i][0]
        y1 = pts_1[i][1]

        x2 = pts_2[i][0]
        y2 = pts_2[i][1]

        p1 = Point(x1, y1)
        p2 = Point(x2, y2)

        X = tri.LinearTriangulation(P1, p1, P2, p2)

        points3d.append(X[1])

    return points3d


# expects normalised points
def triangulateCV(KP1, KP2, pts_1, pts_2):

    points4d = cv2.triangulatePoints(KP1, KP2, pts_1.T, pts_2.T)
    points4d = points4d.T
    points3d = convertFromHomogeneous(points4d)
    points3d = points3d.tolist()

    return points3d


# because openCV is stupid
def convertFromHomogeneous(points):
    new = []
    for p in points:
        s = 1 / p[3]
        n = (s * p[0], s * p[1], s * p[2])
        new.append(n)

    new = np.array(new, dtype='float32')
    return new


# given corners 1, 2, 3, 4, work out the 3d scale factor.
def getScale(goalPosts):
    p1 = goalPosts[0]  # bottom left
    p2 = goalPosts[1]  # top left
    p3 = goalPosts[2]  # top right
    p4 = goalPosts[3]  # bottom right

    distances = []

    leftBar = sep3D(p1, p2)
    crossbar = sep3D(p2, p3)
    rightBar = sep3D(p3, p4)
    baseline = sep3D(p1, p4)

    print "left uprights:", leftBar, rightBar
    print "crossbars:", crossbar, baseline

    distances = [leftBar, rightBar, baseline, crossbar]

    a = (crossbar + baseline) / 2
    b = (leftBar + rightBar) / 2

    scale_a = 7.32 / a
    scale_b = 2.44 / b

    print "crossbar and bar scales:", scale_a, scale_b
    scale = (scale_a + scale_b) / 2

    print "avg scale:", scale

    return scale


# distance between two 3d coordinates
def sep3D(a, b):
    xa = a[0]
    ya = a[1]
    za = a[2]

    xb = b[0]
    yb = b[1]
    zb = b[2]

    dist = math.sqrt(((xa - xb) ** 2) + ((ya - yb) ** 2) + ((za - zb) ** 2))

    return dist


def reconstructionError(original, reconstructed):
    seps = []
    for o, r in zip(original, reconstructed):
        sep = sep3D(o, r)
        print ""
        print o
        print r
        print sep
        seps.append(sep)

    print sum(seps), '/', len(seps)
    avg = sum(seps) / len(seps)
    # avg = np.mean(seps)
    std = np.std(seps)
    outfile = open('tests/' + folder + statdir + 'reconstruction.txt', 'w')
    outfile.write('avg: ' + str(avg) + '\nstd: ' + str(std))
    outfile.close()


# used for checking the triangulation - provide UNNORMALISED DATA
def reprojectionError(K1, P1_mat, K2, P2_mat, pts_3, pts_4, points3d):

    # Nx4 array for filling with homogeneous points
    new = np.zeros((len(points3d), 4))

    for i, point in enumerate(points3d):
        new[i][0] = point[0]
        new[i][1] = point[1]
        new[i][2] = point[2]
        new[i][3] = 1

    errors1 = []
    errors2 = []
    reprojected1 = []
    reprojected2 = []

    # for each 3d point
    for i, X in enumerate(new):
        # x_2d = K * P * X_3d
        xp1 = K1 * P1_mat * np.mat(X).T
        xp2 = K2 * P2_mat * np.mat(X).T

        # normalise the projected (homogenous) coordinates
        # (x,y,1) = (xz,yz,z) / z
        xp1 = xp1 / xp1[2]
        xp2 = xp2 / xp2[2]

        reprojected1.append(xp1)
        reprojected2.append(xp2)

        # and get the orginally measured points
        x1 = pts_3[i]
        x2 = pts_4[i]

        # difference between them is:
        dist1 = math.hypot(xp1[0] - x1[0], xp1[1] - x1[1])
        dist2 = math.hypot(xp2[0] - x2[0], xp2[1] - x2[1])
        errors1.append(dist1)
        errors2.append(dist2)

    avg1 = sum(errors1) / len(errors1)
    avg2 = sum(errors2) / len(errors2)

    std1 = np.std(errors1)
    std2 = np.std(errors2)

    errors = errors1 + errors2
    avg = np.mean(errors)
    std = np.std(errors)

    print "\n> average reprojection error in image 1:", avg1
    print "\n> average reprojection error in image 2:", avg2

    if view:
        plot.plotOrderedBar(
            errors1, 'Reprojection Error Image 1', 'Index', 'px')
        plot.plotOrderedBar(
            errors2, 'Reprojection Error Image 2', 'Index', 'px')

        plot.plot2D(reprojected1, pts_3,
                    'Reprojection of Reconstruction onto Image 1')
        plot.plot2D(reprojected2, pts_4,
                    'Reprojection of Reconstruction onto Image 2')

    outfile = open('tests/' + folder + statdir + 'reprojection.txt', 'w')
    string = 'avg:' + str(avg) + '\nstd:' + str(std)
    outfile.write(string)
    outfile.close()
    print "statfile:", avg, std
    statfile.write(str(avg) + ' ' + str(std) + ' ')


def BoringCameraArray():
    P = np.zeros((3, 4), dtype='float32')
    P[0][0] = 1
    P[1][1] = 1
    P[2][2] = 1
    return P


# P = [R|t]
def CameraArray(R, t):
    # just tack t on as a column to the end of R
    P = np.zeros((3, 4), dtype='float32')
    P[0][0] = R[0, 0]
    P[0][1] = R[0, 1]
    P[0][2] = R[0, 2]
    P[0][3] = t[0]

    P[1][0] = R[1, 0]
    P[1][1] = R[1, 1]
    P[1][2] = R[1, 2]
    P[1][3] = t[1]

    P[2][0] = R[2, 0]
    P[2][1] = R[2, 1]
    P[2][2] = R[2, 2]
    P[2][3] = t[2]

    return P


# given a set of point correspondences x x', adjust the alignment such
# that x'Fx = 0 is smallest. obeys the geometry most closely.
def synchroniseGeometric(pts_1, pts_2, F):

    print "> GEOMETRIC SYNCHRONISATION:"

    syncd1 = []
    syncd2 = []
    shorter = []
    longer = []
    short_flag = 0

    if len(pts_1) < len(pts_2):
        shorter = pts_1
        longer = pts_2
        short_flag = 1
    else:
        shorter = pts_2
        longer = pts_1
        short_flag = 2

    diff = len(longer) - len(shorter)
    print "Longer:", len(longer)
    print "Shorter:", len(shorter)
    print "Diff:", diff

    shorter_hom = cv2.convertPointsToHomogeneous(shorter)
    longer_hom = cv2.convertPointsToHomogeneous(longer)

    averages = []

    for offset in xrange(0, diff + 1):
        err = 0
        avg = 0
        print ""
        for i in xrange(0, len(shorter)):
            a = shorter_hom[i]
            b = longer_hom[i + offset]
            this_err = abs(np.mat(a) * F * np.mat(b).T)
            err += this_err
            print this_err

        avg = err / len(shorter)
        # print "Offset, Err:", offset, avg
        avg_off = (avg, offset)
        averages.append(avg_off)

    m = min(float(a[0]) for a in averages)

    ret = [item for item in averages if item[0] == m]

    print "Minimum:", m
    print "Offset:", ret[0][1]

    # trim the beginning of the longer list
    offset = ret[0][1]
    longer = longer[offset:]

    # trim its end
    tail = len(longer) - len(shorter)
    if tail != 0:
        longer = longer[:-tail]

    if short_flag == 1:
        syncd1 = shorter
        syncd2 = longer
    else:
        syncd1 = longer
        syncd2 = shorter

    print "Synched Trajectory Length:", len(longer), len(shorter)

    if view:
        plot.plot2D(syncd1, name='First Synced Trajectory')
        plot.plot2D(syncd2, name='Second Synced Trajectory')

    return syncd1, syncd2


# Copyright 2013, Alexander Mordvintsev & Abid K
def autoGetCorrespondences(img1, img2):
    sift = cv2.SIFT()

    # find the keypoints and descriptors with SIFT
    kp1, des1 = sift.detectAndCompute(img1, None)
    kp2, des2 = sift.detectAndCompute(img2, None)

    # FLANN parameters
    FLANN_INDEX_KDTREE = 0
    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    search_params = dict(checks=50)

    flann = cv2.FlannBasedMatcher(index_params, search_params)
    matches = flann.knnMatch(des1, des2, k=2)

    good = []
    auto_pts1 = []
    auto_pts2 = []

    # ratio test as per Lowe's paper
    for i, (m, n) in enumerate(matches):
        if m.distance < 0.8 * n.distance:
            good.append(m)
            auto_pts2.append(kp2[m.trainIdx].pt)
            auto_pts1.append(kp1[m.queryIdx].pt)

    return np.float32(auto_pts1), np.float32(auto_pts2)


def autoGetF():
    img1 = cv2.imread('../res/mvb/d5000.png', 0)
    img2 = cv2.imread('../res/mvb/g3.png', 0)

    auto_pts1, auto_pts2 = autoGetCorrespondences(img1, img2)

    F, mask = cv2.findFundamentalMat(auto_pts1, auto_pts2, cv2.FM_LMEDS)

    # We select only inlier points
    auto_pts1 = auto_pts1[mask.ravel() == 1]
    auto_pts2 = auto_pts2[mask.ravel() == 1]

    return F, auto_pts1, auto_pts2


# ----------------------------------------------------------------------
# ------------------- MAIN PROGRAM STARTS HERE -------------------------
# ----------------------------------------------------------------------

# INITIALISE ANY GLOBALLY AVAILABLE DATA
try:
    folder = sys.argv[1]
except IndexError:
    folder = 1

if folder.isdigit() or folder == 'errors':
    simulation = True

# Calibration matrices:
if folder == 'coombe_sim':
    print "-----Shot Simulation 1------"
    K1 = np.mat(tools.CalibArray(1000, 640, 360), dtype='float32')
    K2 = np.mat(tools.CalibArray(1000, 640, 360), dtype='float32')

elif folder == 'coombe_sim2':
    print "-----Shot Simulation 2------"
    K1 = np.mat(tools.CalibArray(1000, 640, 360), dtype='float32')
    K2 = np.mat(tools.CalibArray(1000, 640, 360), dtype='float32')

else:
    K1 = np.mat(tools.CalibArray(950, 640, -360), dtype='float32')  # lumix
    K2 = np.mat(tools.CalibArray(1091, 640, -360), dtype='float32')  # g3

# If one of the simulation folders, set the calib matrices to sim values
if simulation:
    K1 = np.mat(tools.CalibArray(1000, 640, 360), dtype='float32')
    K2 = np.mat(tools.CalibArray(1000, 640, 360), dtype='float32')

noise = 0
try:
    noise = float(sys.argv[2])
except IndexError:
    pass

statdir = '/stats/'

if not os.path.exists('tests/' + folder + statdir):
    os.makedirs('tests/' + folder + statdir)

statfile = open('tests/' + folder + statdir + 'run10.txt', 'w')
statfile.write(
    'N GaussianNoiseScale MeanNoiseMag MeanPLineDist Std MeanRepErr Std StdRec\n')

# write a noise loop here
# for n in xrange(0, 30):
#     noise = n

# get the data completely resh from file
data3D, pts1_raw, pts2_raw, pts3_raw, pts4_raw, postPts1, postPts2, rec_data = getData(
    folder)

pts1 = []
pts2 = []
pts3 = []
pts4 = []

# Image coords: (x, y)
pts1 = np.array(pts1_raw, dtype='float32')
pts2 = np.array(pts2_raw, dtype='float32')
pts3 = np.array(pts3_raw, dtype='float32')
pts4 = np.array(pts4_raw, dtype='float32')
postPts1 = np.array(postPts1, dtype='float32')
postPts2 = np.array(postPts2, dtype='float32')

N = len(pts1)
print "statfile:", N
statfile.write(str(N) + ' ')

print "statfile:", noise
statfile.write(str(noise) + ' ')

# NOISE
if noise != 0:
    print "Add Noise:", noise
    pts1, avg_mag1 = addNoise(noise, pts1)
    pts2, avg_mag2 = addNoise(noise, pts2)
    avg_mag = (avg_mag1 + avg_mag2) / 2
    print "statfile:", avg_mag
    statfile.write(str(avg_mag) + ' ')

# using the trajectories themselves to calculate geometry
if rec_data is False and simulation is False:
    pts1, pts2 = synchroniseAtApex(pts1, pts2)
    pts3, pts4 = synchroniseAtApex(pts3, pts4)

# Normalised homogenous image coords: (x, y, 1)
norm_pts1 = tools.normalise_homogenise(pts1, K1)
norm_pts2 = tools.normalise_homogenise(pts2, K2)

# Inhomogenous but normalised K_inv(x, y) (for if you want to calc E
# directly)
inhomog_norm_pts1 = np.delete(norm_pts1, 2, 1)
inhomog_norm_pts2 = np.delete(norm_pts2, 2, 1)

# Arrays FOR Rt computation
W, W_inv, Z = tools.initWZarrays()  # HZ 9.13

run()

statfile.close()
print "---------------------------------------------"
