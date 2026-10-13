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
