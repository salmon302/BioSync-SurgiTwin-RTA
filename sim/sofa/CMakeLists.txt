# SOFA FEM scene sources (FR-MS-002, FR-MS-003, task 2.2).
#
# This directory is added only when the root option SRTA_BUILD_SOFA=ON
# (default OFF), so a default configure never runs the find logic below.
# There are no link targets yet: the check locates the pinned SOFA install
# and reports its version so the procurement guide Section 2 configure
# check has evidence. Scene sources are under src/ and are run through
# runSofa.exe, not built here. See README.md.
#
# FindSOFA.cmake validates the package config file the install ships
# (lib/cmake/Sofa.Framework/Sofa.FrameworkConfig.cmake, version file reports
# 26.06.00) and reads its version. A plain find_package(Sofa.Framework
# CONFIG) aborts on this install because its imported-target files verify
# <root>/bin/*.dll while the binaries live in <root>/collections/bin; the
# module records that limitation.
#
# Configure check (procurement guide Section 2):
#   cmake -S . -B build\sofa-check -DSRTA_BUILD_SOFA=ON ^
#         -DSofa_DIR=C:\Users\salmo\SOFA\v26.06.00\lib\cmake\Sofa.Framework

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

find_package(SOFA MODULE)

if(NOT SOFA_FOUND)
  message(FATAL_ERROR
    "SRTA_BUILD_SOFA=ON but the SOFA install was not found. Pass "
    "-DSofa_DIR=<install>/lib/cmake/Sofa.Framework or -DSRTA_SOFA_ROOT=<install> "
    "(or set the SOFA_ROOT environment variable). Pinned release: v26.06.00 (sim/SOUP.md).")
endif()

message(STATUS "SurgiTwin-RTA: SOFA ${SOFA_VERSION} at ${SOFA_ROOT_DIR}")