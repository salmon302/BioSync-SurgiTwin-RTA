add_library(srta_rta
  src/safety_envelope.cpp
  src/simplex_switch.cpp
  src/timed_automata.cpp
)
target_include_directories(srta_rta PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_features(srta_rta PUBLIC cxx_std_17)

add_executable(srta_rta_test_smoke tests/test_smoke.cpp)
target_link_libraries(srta_rta_test_smoke PRIVATE srta_rta)
add_test(NAME rta_smoke COMMAND srta_rta_test_smoke)

option(SRTA_BUILD_RTA_TESTS "Build the Catch2 unit suite (pinned Catch2 v3.9.1, plan task 3.8)" ON)
if(SRTA_BUILD_RTA_TESTS)
  include(FetchContent)
  # Catch2 v3.9.1, BSL-1.0. Same pin as sim/fmi/master/CMakeLists.txt; hashes and the
  # offline rebuild route are recorded in rta/tests/pins.json.
  FetchContent_Declare(Catch2
    URL https://github.com/catchorg/Catch2/archive/refs/tags/v3.9.1.tar.gz
    URL_HASH SHA256=A215C2A723BD7483EFD236DC86066842A389CB4E344C61119C978ACDF24D39BE
  )
  set(CATCH_INSTALL_DOCS OFF CACHE BOOL "" FORCE)
  set(CATCH_INSTALL_EXTRAS OFF CACHE BOOL "" FORCE)
  set(BUILD_SHARED_LIBS OFF)
  FetchContent_MakeAvailable(Catch2)

  add_executable(srta_rta_unit_tests
    tests/test_safety_envelope.cpp
    tests/test_simplex_switch.cpp
    tests/test_timed_automata.cpp
  )
  target_link_libraries(srta_rta_unit_tests PRIVATE srta_rta Catch2::Catch2WithMain)
  target_compile_features(srta_rta_unit_tests PRIVATE cxx_std_17)
  add_test(NAME rta_unit COMMAND srta_rta_unit_tests)
endif()
