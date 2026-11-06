# SPDX-License-Identifier: MIT
# FMI 3.0 FMU packaging (SRS FR-MS-007, plan task 2.7). Slice 1: thermal_pennes.
#
# Standalone configure (no root project build):
#   cmake -S sim/fmi -B sim/fmi/build -A x64
# Root configure: cmake -S . -B build -DSRTA_BUILD_FMI=ON
# Use sim/fmi/build.ps1 to configure, build, and stage the FMU in one command.

cmake_minimum_required(VERSION 3.16)
project(srta_fmi VERSION 0.1.0 LANGUAGES C)

set(SRTA_FMI_FMU_NAME "thermal_pennes")
set(SRTA_FMI_FMU_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}/fmu")

add_library(${SRTA_FMI_FMU_NAME} SHARED
  src/thermal_pennes.c
  src/fmi3_unsupported.c
)

set_target_properties(${SRTA_FMI_FMU_NAME} PROPERTIES
  C_STANDARD 99
  C_STANDARD_REQUIRED ON
  C_EXTENSIONS OFF
  PREFIX ""
  OUTPUT_NAME "${SRTA_FMI_FMU_NAME}"
)

target_include_directories(${SRTA_FMI_FMU_NAME} PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}/include/fmi3"
)

if(MSVC)
  target_compile_options(${SRTA_FMI_FMU_NAME} PRIVATE /W4 /WX /permissive-)
else()
  target_compile_options(${SRTA_FMI_FMU_NAME} PRIVATE -Wall -Wextra -Werror -pedantic)
endif()

# Stage the FMI 3.0 directory layout and zip it into <name>.fmu. The archive
# holds modelDescription.xml and binaries/x86_64-windows/<name>.dll.
file(MAKE_DIRECTORY "${SRTA_FMI_FMU_OUTPUT_DIR}/stage/binaries/x86_64-windows")

add_custom_command(TARGET ${SRTA_FMI_FMU_NAME} POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E make_directory "${SRTA_FMI_FMU_OUTPUT_DIR}/stage/binaries/x86_64-windows"
  COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_CURRENT_SOURCE_DIR}/model/modelDescription.xml"
          "${SRTA_FMI_FMU_OUTPUT_DIR}/stage/modelDescription.xml"
  COMMAND ${CMAKE_COMMAND} -E copy "$<TARGET_FILE:${SRTA_FMI_FMU_NAME}>"
          "${SRTA_FMI_FMU_OUTPUT_DIR}/stage/binaries/x86_64-windows/${SRTA_FMI_FMU_NAME}.dll"
  COMMAND ${CMAKE_COMMAND} -E rm -f "${SRTA_FMI_FMU_OUTPUT_DIR}/${SRTA_FMI_FMU_NAME}.fmu"
  COMMAND ${CMAKE_COMMAND} -E tar cf "${SRTA_FMI_FMU_OUTPUT_DIR}/${SRTA_FMI_FMU_NAME}.fmu"
          --format=zip -- modelDescription.xml binaries/x86_64-windows/${SRTA_FMI_FMU_NAME}.dll
  WORKING_DIRECTORY "${SRTA_FMI_FMU_OUTPUT_DIR}/stage"
  VERBATIM
)
