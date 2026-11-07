# SPDX-License-Identifier: MIT
# FMI 3.0 FMU packaging (SRS FR-MS-007, plan tasks 2.7 slices 1 and 2).
#
# Targets:
#   thermal_pennes   C, Pennes bioheat ablation FMU (slice 1). Archive: modelDescription.xml and the DLL.
#   mechanical_sofa  C++17, SOFA reference-organ FMU proxy (slice 2). Archive: modelDescription.xml, the DLL,
#                    resources/mechanical_worker.py, and resources/meshes/reference_organ.msh. The SOFA runtime
#                    is a host dependency (runSofa.exe with SofaPython3), not part of the archive.
#
# Standalone configure (no root project build):
#   cmake -S sim/fmi -B sim/fmi/build -A x64
# Root configure: cmake -S . -B build -DSRTA_BUILD_FMI=ON
# Use sim/fmi/build.ps1 to configure, build, and stage both FMUs in one command.

cmake_minimum_required(VERSION 3.16)
project(srta_fmi VERSION 0.1.0 LANGUAGES C CXX)

set(SRTA_FMI_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/include/fmi3")
set(SRTA_FMI_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}/fmu")

# Stage a directory tree from the list of "source|archive_path" pairs and zip it into <name>.fmu.
# Arguments: target fmu_name model_xml, then zero or more "source|archive_path" resource pairs.
function(srta_fmi_package_fmu target fmu_name model_xml)
  set(stage "${SRTA_FMI_OUTPUT_DIR}/stage-${fmu_name}")
  file(MAKE_DIRECTORY "${stage}")
  set(commands)
  list(APPEND commands
    COMMAND ${CMAKE_COMMAND} -E make_directory "${stage}/binaries/x86_64-windows"
    COMMAND ${CMAKE_COMMAND} -E copy "${model_xml}" "${stage}/modelDescription.xml"
    COMMAND ${CMAKE_COMMAND} -E copy "$<TARGET_FILE:${target}>"
            "${stage}/binaries/x86_64-windows/${fmu_name}.dll")
  set(archive_members modelDescription.xml binaries/x86_64-windows/${fmu_name}.dll)
  foreach(pair IN LISTS ARGN)
    string(REPLACE "|" ";" parts "${pair}")
    list(GET parts 0 source_file)
    list(GET parts 1 archive_path)
    get_filename_component(archive_dir "${stage}/${archive_path}" DIRECTORY)
    list(APPEND commands
      COMMAND ${CMAKE_COMMAND} -E make_directory "${archive_dir}"
      COMMAND ${CMAKE_COMMAND} -E copy "${source_file}" "${stage}/${archive_path}")
    list(APPEND archive_members ${archive_path})
  endforeach()
  add_custom_command(TARGET ${target} POST_BUILD
    ${commands}
    COMMAND ${CMAKE_COMMAND} -E rm -f "${SRTA_FMI_OUTPUT_DIR}/${fmu_name}.fmu"
    COMMAND ${CMAKE_COMMAND} -E tar cf "${SRTA_FMI_OUTPUT_DIR}/${fmu_name}.fmu"
            --format=zip -- ${archive_members}
    WORKING_DIRECTORY "${stage}"
    VERBATIM
  )
endfunction()

# thermal_pennes (slice 1, unchanged behavior)
add_library(thermal_pennes SHARED src/thermal_pennes.c src/fmi3_unsupported.c)
set_target_properties(thermal_pennes PROPERTIES
  C_STANDARD 99
  C_STANDARD_REQUIRED ON
  C_EXTENSIONS OFF
  PREFIX ""
  OUTPUT_NAME "thermal_pennes"
)
target_include_directories(thermal_pennes PRIVATE "${SRTA_FMI_INCLUDE_DIR}")
if(MSVC)
  target_compile_options(thermal_pennes PRIVATE /W4 /WX /permissive-)
else()
  target_compile_options(thermal_pennes PRIVATE -Wall -Wextra -Werror -pedantic)
endif()
srta_fmi_package_fmu(thermal_pennes thermal_pennes "${CMAKE_CURRENT_SOURCE_DIR}/model/modelDescription.xml")

# mechanical_sofa (slice 2): C++17 proxy DLL and the fmi3 stubs (shared with thermal_pennes).
add_library(mechanical_sofa SHARED mechanical/src/mechanical_sofa.cpp src/fmi3_unsupported.c)
set_target_properties(mechanical_sofa PROPERTIES
  CXX_STANDARD 17
  CXX_STANDARD_REQUIRED ON
  CXX_EXTENSIONS OFF
  C_STANDARD 99
  C_STANDARD_REQUIRED ON
  PREFIX ""
  OUTPUT_NAME "mechanical_sofa"
)
target_include_directories(mechanical_sofa PRIVATE "${SRTA_FMI_INCLUDE_DIR}")
target_compile_definitions(mechanical_sofa PRIVATE
  "SRTA_DEFAULT_SOFA_ROOT=\"C:/Users/salmo/SOFA/v26.06.00\""
  "SRTA_DEFAULT_PIXI_ENV=\"${CMAKE_CURRENT_SOURCE_DIR}/../../env/ros2-jazzy/.pixi/envs/default\""
)
if(MSVC)
  target_compile_options(mechanical_sofa PRIVATE /W4 /WX /permissive- /EHsc)
endif()
srta_fmi_package_fmu(mechanical_sofa mechanical_sofa
  "${CMAKE_CURRENT_SOURCE_DIR}/mechanical/model/modelDescription.xml"
  "${CMAKE_CURRENT_SOURCE_DIR}/mechanical/worker/mechanical_worker.py|resources/mechanical_worker.py"
  "${CMAKE_CURRENT_SOURCE_DIR}/../sofa/src/meshes/reference_organ.msh|resources/meshes/reference_organ.msh"
)

# pulse_physiology (slice 3): C++17 proxy DLL (Winsock TCP, MessagePack frames). The engine runs in the
# biosync-pulse container; the worker script is shipped in resources/ and started inside the container.
add_library(pulse_physiology SHARED pulse/src/pulse_physiology.cpp src/fmi3_unsupported.c)
set_target_properties(pulse_physiology PROPERTIES
  CXX_STANDARD 17
  CXX_STANDARD_REQUIRED ON
  CXX_EXTENSIONS OFF
  C_STANDARD 99
  C_STANDARD_REQUIRED ON
  PREFIX ""
  OUTPUT_NAME "pulse_physiology"
)
target_include_directories(pulse_physiology PRIVATE "${SRTA_FMI_INCLUDE_DIR}")
target_link_libraries(pulse_physiology PRIVATE ws2_32)
if(MSVC)
  target_compile_options(pulse_physiology PRIVATE /W4 /WX /permissive- /EHsc)
endif()
srta_fmi_package_fmu(pulse_physiology pulse_physiology
  "${CMAKE_CURRENT_SOURCE_DIR}/pulse/model/modelDescription.xml"
  "${CMAKE_CURRENT_SOURCE_DIR}/pulse/worker/pulse_worker.py|resources/pulse_worker.py"
)
