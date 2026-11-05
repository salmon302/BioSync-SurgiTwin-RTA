cmake_minimum_required(VERSION 3.16)
project(SurgiTwinRTA VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(SRTA_BUILD_RTA "Build the Run-Time Assurance (Simplex) tier" ON)
option(SRTA_BUILD_SOFA "Build the SOFA FEM scene stubs" OFF)
option(SRTA_BUILD_FMI "Build the FMI 3.0 co-simulation stubs" OFF)
option(SRTA_BUILD_BRIDGE "Build the ROS 2 / Fast DDS bridge stubs" OFF)

enable_testing()

if(SRTA_BUILD_RTA)
  add_subdirectory(rta)
endif()

if(SRTA_BUILD_SOFA)
  add_subdirectory(sim/sofa)
endif()

if(SRTA_BUILD_FMI)
  add_subdirectory(sim/fmi)
endif()

if(SRTA_BUILD_BRIDGE)
  add_subdirectory(sim/bridge)
endif()
