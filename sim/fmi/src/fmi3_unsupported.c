// SPDX-License-Identifier: MIT
/*
 * Symbol stubs for FMI 3.0 entry points that the thermal_pennes Co-Simulation
 * FMU does not implement. modelDescription.xml declares no ModelExchange,
 * ScheduledExecution, clock, binary, string, directional derivative, or FMU
 * state capability, so these functions return fmi3Error (3) or a null instance.
 *
 * The stubs are exported because FMPy 0.3.32 binds every FMI 3.0 symbol when it
 * loads the shared library. They are in a separate translation unit so they do
 * not conflict with the prototypes in the pinned fmi3Functions.h.
 */

#if defined(_WIN32) || defined(__CYGWIN__)
#define FMI3_STUB_EXPORT __declspec(dllexport)
#else
#define FMI3_STUB_EXPORT __attribute__((visibility("default")))
#endif

#define FMI3_STUB_ERROR_STATUS 3

#define FMI3_STUB(name) FMI3_STUB_EXPORT int name(void) { return FMI3_STUB_ERROR_STATUS; }
#define FMI3_STUB_INSTANCE(name) FMI3_STUB_EXPORT void *name(void) { return 0; }

FMI3_STUB_INSTANCE(fmi3InstantiateModelExchange)
FMI3_STUB_INSTANCE(fmi3InstantiateScheduledExecution)
FMI3_STUB(fmi3EnterEventMode)

FMI3_STUB(fmi3GetFloat32)
FMI3_STUB(fmi3GetInt8)
FMI3_STUB(fmi3GetUInt8)
FMI3_STUB(fmi3GetInt16)
FMI3_STUB(fmi3GetUInt16)
FMI3_STUB(fmi3GetInt32)
FMI3_STUB(fmi3GetUInt32)
FMI3_STUB(fmi3GetInt64)
FMI3_STUB(fmi3GetUInt64)
FMI3_STUB(fmi3GetBoolean)
FMI3_STUB(fmi3GetString)
FMI3_STUB(fmi3GetBinary)
FMI3_STUB(fmi3GetClock)

FMI3_STUB(fmi3SetFloat32)
FMI3_STUB(fmi3SetInt8)
FMI3_STUB(fmi3SetUInt8)
FMI3_STUB(fmi3SetInt16)
FMI3_STUB(fmi3SetUInt16)
FMI3_STUB(fmi3SetInt32)
FMI3_STUB(fmi3SetUInt32)
FMI3_STUB(fmi3SetInt64)
FMI3_STUB(fmi3SetUInt64)
FMI3_STUB(fmi3SetBoolean)
FMI3_STUB(fmi3SetString)
FMI3_STUB(fmi3SetBinary)
FMI3_STUB(fmi3SetClock)

FMI3_STUB(fmi3GetNumberOfVariableDependencies)
FMI3_STUB(fmi3GetVariableDependencies)

FMI3_STUB(fmi3GetFMUState)
FMI3_STUB(fmi3SetFMUState)
FMI3_STUB(fmi3FreeFMUState)
FMI3_STUB(fmi3SerializedFMUStateSize)
FMI3_STUB(fmi3SerializeFMUState)
FMI3_STUB(fmi3DeserializeFMUState)

FMI3_STUB(fmi3GetDirectionalDerivative)
FMI3_STUB(fmi3GetAdjointDerivative)

FMI3_STUB(fmi3EnterConfigurationMode)
FMI3_STUB(fmi3ExitConfigurationMode)

FMI3_STUB(fmi3GetIntervalDecimal)
FMI3_STUB(fmi3GetIntervalFraction)
FMI3_STUB(fmi3GetShiftDecimal)
FMI3_STUB(fmi3GetShiftFraction)
FMI3_STUB(fmi3SetIntervalDecimal)
FMI3_STUB(fmi3SetIntervalFraction)
FMI3_STUB(fmi3SetShiftDecimal)
FMI3_STUB(fmi3SetShiftFraction)

FMI3_STUB(fmi3EvaluateDiscreteStates)
FMI3_STUB(fmi3UpdateDiscreteStates)

FMI3_STUB(fmi3EnterContinuousTimeMode)
FMI3_STUB(fmi3CompletedIntegratorStep)
FMI3_STUB(fmi3SetTime)
FMI3_STUB(fmi3SetContinuousStates)
FMI3_STUB(fmi3GetContinuousStateDerivatives)
FMI3_STUB(fmi3GetEventIndicators)
FMI3_STUB(fmi3GetContinuousStates)
FMI3_STUB(fmi3GetNominalsOfContinuousStates)
FMI3_STUB(fmi3GetNumberOfEventIndicators)
FMI3_STUB(fmi3GetNumberOfContinuousStates)

FMI3_STUB(fmi3EnterStepMode)
FMI3_STUB(fmi3GetOutputDerivatives)
FMI3_STUB(fmi3ActivateModelPartition)
