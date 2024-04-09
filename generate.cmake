include_guard()

cmake_minimum_required(VERSION 3.17 FATAL_ERROR)

function(generate_msg)
    set(oneValueArgs)
    set(options)
    set(multiValueArgs)
    cmake_parse_arguments(ARG
        "${options}"
        "${oneValueArgs}"
        "${multiValueArgs}"
        ${ARGN})
    set(script ${CMAKE_CURRENT_FUNCTION_LIST_DIR}/generate.py)
endfunction()