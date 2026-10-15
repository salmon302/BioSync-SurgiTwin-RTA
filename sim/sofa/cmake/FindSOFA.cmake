# FindSOFA.cmake - locate the pinned SOFA binary install (task 2.2).
#
# Why a find module instead of find_package(Sofa.Framework CONFIG): the
# v26.06.00 Windows install ships the per-module package config files under
# <root>/lib/cmake/<Module>/, but their imported-target files verify
# <root>/bin/<Module>.dll while the installer collects the binaries under
# <root>/collections/bin. Including Sofa.FrameworkConfig.cmake therefore
# aborts the configure with a missing-imported-file FATAL_ERROR. This module
# validates the package config file the install actually ships
# (Sofa.FrameworkConfig.cmake), reads the shipped version file for the
# version report, and locates runSofa.exe in the observed layout.
#
# Inputs (cache variables):
#   Sofa_DIR       - directory holding Sofa.FrameworkConfig.cmake. This is
#                    the variable named in docs/procurement-guide.md Section 2.
#   SRTA_SOFA_ROOT - install root (e.g. C:/Users/salmo/SOFA/v26.06.00);
#                    used when Sofa_DIR is empty.
#   SOFA_ROOT      - environment variable fallback for the install root.
#
# Outputs:
#   SOFA_FOUND, SOFA_VERSION, SOFA_PACKAGE_DIR, SOFA_ROOT_DIR, SOFA_RUNSOFA

include(FindPackageHandleStandardArgs)

set(_sofa_package_dir "")
set(_sofa_root_dir "")

if(Sofa_DIR)
  set(_sofa_package_dir "${Sofa_DIR}")
elseif(SRTA_SOFA_ROOT)
  set(_sofa_root_dir "${SRTA_SOFA_ROOT}")
  set(_sofa_package_dir "${SRTA_SOFA_ROOT}/lib/cmake/Sofa.Framework")
elseif(DEFINED ENV{SOFA_ROOT} AND NOT "$ENV{SOFA_ROOT}" STREQUAL "")
  set(_sofa_root_dir "$ENV{SOFA_ROOT}")
  set(_sofa_package_dir "$ENV{SOFA_ROOT}/lib/cmake/Sofa.Framework")
endif()

set(SOFA_PACKAGE_DIR "${_sofa_package_dir}")
set(SOFA_VERSION "")
set(SOFA_RUNSOFA "")
set(SOFA_ROOT_DIR "")

if(_sofa_package_dir)
  get_filename_component(_sofa_root_from_package "${_sofa_package_dir}/../../.." ABSOLUTE)
  if(NOT _sofa_root_dir)
    set(_sofa_root_dir "${_sofa_root_from_package}")
  endif()

  # The package config file the install ships must exist; this is the file
  # the procurement guide's -DSofa_DIR value points at.
  if(EXISTS "${_sofa_package_dir}/Sofa.FrameworkConfig.cmake"
     AND EXISTS "${_sofa_package_dir}/Sofa.FrameworkConfigVersion.cmake")
    file(READ "${_sofa_package_dir}/Sofa.FrameworkConfigVersion.cmake" _sofa_version_text)
    string(REGEX MATCH "set\\(PACKAGE_VERSION \"[0-9.]+\"" _sofa_version_match
           "${_sofa_version_text}")
    if(_sofa_version_match)
      string(REGEX REPLACE ".*\"([0-9.]+)\"" "\\1" SOFA_VERSION "${_sofa_version_match}")
    endif()
    set(SOFA_ROOT_DIR "${_sofa_root_from_package}")
    # Observed layout: binaries under collections/bin; accept a classic bin/ too.
    if(EXISTS "${SOFA_ROOT_DIR}/collections/bin/runSofa.exe")
      set(SOFA_RUNSOFA "${SOFA_ROOT_DIR}/collections/bin/runSofa.exe")
    elseif(EXISTS "${SOFA_ROOT_DIR}/bin/runSofa.exe")
      set(SOFA_RUNSOFA "${SOFA_ROOT_DIR}/bin/runSofa.exe")
    endif()
  endif()
endif()

find_package_handle_standard_args(SOFA
  REQUIRED_VARS SOFA_PACKAGE_DIR SOFA_VERSION SOFA_RUNSOFA
  VERSION_VAR SOFA_VERSION)

if(SOFA_FOUND)
  message(STATUS "SOFA found: version ${SOFA_VERSION} (package dir ${SOFA_PACKAGE_DIR})")
  message(STATUS "SOFA runSofa: ${SOFA_RUNSOFA}")
endif()

mark_as_advanced(SOFA_PACKAGE_DIR SOFA_ROOT_DIR SOFA_RUNSOFA)