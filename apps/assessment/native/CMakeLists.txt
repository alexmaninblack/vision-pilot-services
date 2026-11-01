# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.22)
project(vision_assessment_native LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
find_path(OPENCV_INCLUDE_DIR opencv2/core.hpp PATH_SUFFIXES opencv4 REQUIRED)
find_library(OPENCV_CORE_LIBRARY opencv_core REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(IPOPT REQUIRED ipopt)
find_path(CPPAD_INCLUDE_DIR cppad/cppad.hpp REQUIRED)
find_library(CPPAD_LIBRARY cppad_lib)
get_filename_component(ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
set(UPSTREAM "${ROOT}/third_party/vision_pilot/VisionPilot/modules")
add_library(vision_assessment SHARED assessment.cpp
    "${UPSTREAM}/safety_guardian/fusion/src/longitudinal_fusion.cpp"
    "${UPSTREAM}/safety_guardian/fusion/src/lateral_fusion.cpp"
    "${UPSTREAM}/safety_guardian/planning/src/planning.cpp"
    "${UPSTREAM}/safety_guardian/planning/src/longitudinal_planning.cpp"
    "${UPSTREAM}/safety_guardian/planning/src/lateral_planning.cpp")
target_include_directories(vision_assessment PRIVATE include ${OPENCV_INCLUDE_DIR} ${IPOPT_INCLUDE_DIRS} ${CPPAD_INCLUDE_DIR}
    "${UPSTREAM}/common/include" "${UPSTREAM}/models/include"
    "${UPSTREAM}/safety_guardian/fusion/include" "${UPSTREAM}/safety_guardian/planning/include")
target_compile_definitions(vision_assessment PRIVATE HAVE_CSTDDEF)
target_compile_options(vision_assessment PRIVATE -Wall -Wextra)
target_link_libraries(vision_assessment PRIVATE ${OPENCV_CORE_LIBRARY} ${IPOPT_LIBRARIES} Eigen3::Eigen)
if(CPPAD_LIBRARY)
    target_link_libraries(vision_assessment PRIVATE ${CPPAD_LIBRARY})
endif()
set_target_properties(vision_assessment PROPERTIES BUILD_RPATH_USE_ORIGIN TRUE INSTALL_RPATH "$ORIGIN")
