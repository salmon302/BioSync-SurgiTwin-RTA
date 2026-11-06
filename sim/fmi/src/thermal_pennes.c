// SPDX-License-Identifier: MIT
/*
 * Pennes bioheat thermal ablation plant model, FMI 3.0 Co-Simulation FMU.
 * Plan task 2.7 slice 1 (SRS FR-MS-007). Equations, parameters, sources, and
 * the stability bound are documented in sim/fmi/README.md.
 *
 * All state arrays are allocated in fmi3InstantiateCoSimulation. fmi3DoStep
 * performs one explicit Euler step and does not allocate.
 */

#include <math.h>
#include <string.h>

#include "fmi3Functions.h"

#define NX 16
#define NY 16
#define NZ 16
#define NCELL (NX * NY * NZ)

#define SOLVER_DT 0.1
#define KELVIN_OFFSET 273.15
#define T_LESION_K (60.0 + KELVIN_OFFSET)
#define CEM43_LESION_MIN 240.0
#define CEM43_T_BREAK_C 43.0
#define CEM43_R_HOT 0.5
#define CEM43_R_COLD 0.25
#define STABILITY_LIMIT 1.0
#define GUID_TOKEN "5d6f2a8e-3c1b-4f7a-9e2d-7b8c0a1f4e63"

enum {
    VR_TIME = 0,
    VR_RHO = 1,
    VR_C = 2,
    VR_K = 3,
    VR_WB = 4,
    VR_CB = 5,
    VR_TA = 6,
    VR_QMET = 7,
    VR_DX = 8,
    VR_RAPP = 9,
    VR_TINIT = 10,
    VR_PABL = 11,
    VR_HBC = 12,
    VR_TENV = 13,
    VR_TMAX = 20,
    VR_TMEAN = 21,
    VR_V60 = 22,
    VR_VLES = 23
};

enum { STATE_CONFIG = 0, STATE_INIT = 1, STATE_STEPPING = 2, STATE_TERMINATED = 3 };

typedef struct {
    fmi3InstanceEnvironment env;
    fmi3LogMessageCallback logMessage;
    fmi3Boolean loggingOn;
    int state;

    double t;
    double rho, c, k, wb, cb, Ta, Qmet, dx, rapp, Tinit;
    double Pabl, hbc, Tenv;
    double Tmax, Tmean, V60, Vles;

    double *T;
    double *Tn;
    double cem[NCELL];
    double bufA[NCELL];
    double bufB[NCELL];
    double shape[NCELL];
    unsigned char nbnd[NCELL];
} Model;

static void log_msg(Model *m, fmi3Status status, const char *msg) {
    if (m && m->logMessage) {
        m->logMessage(m->env, status, "thermal_pennes", msg);
    }
}

static size_t cell_index(int i, int j, int k) {
    return ((size_t)k * NY + (size_t)j) * NX + (size_t)i;
}

static void compute_outputs(Model *m) {
    double tmax = -1.0e300;
    double tsum = 0.0;
    size_t n60 = 0;
    size_t nles = 0;
    for (size_t q = 0; q < NCELL; q++) {
        double v = m->T[q];
        if (v > tmax) tmax = v;
        tsum += v;
        if (v >= T_LESION_K) n60++;
        if (m->cem[q] >= CEM43_LESION_MIN) nles++;
    }
    double cell_mm3 = m->dx * m->dx * m->dx * 1.0e9;
    m->Tmax = tmax;
    m->Tmean = tsum / (double)NCELL;
    m->V60 = (double)n60 * cell_mm3;
    m->Vles = (double)nles * cell_mm3;
}

static int stability_ok(const Model *m) {
    double inv_rc = 1.0 / (m->rho * m->c);
    double lambda = 12.0 * (m->k * inv_rc) / (m->dx * m->dx)
                  + m->wb * m->cb * inv_rc
                  + 3.0 * m->hbc * inv_rc / m->dx;
    return SOLVER_DT * lambda <= STABILITY_LIMIT;
}

static int params_valid(const Model *m) {
    return m->rho > 0.0 && m->c > 0.0 && m->k > 0.0 && m->wb >= 0.0 && m->cb > 0.0
        && m->dx > 0.0 && m->rapp > 0.0 && m->Ta > 0.0 && m->Tinit > 0.0
        && m->hbc >= 0.0 && m->Tenv > 0.0;
}

static void build_geometry(Model *m) {
    int nsphere = 0;
    double r2 = m->rapp * m->rapp;
    for (int k = 0; k < NZ; k++) {
        for (int j = 0; j < NY; j++) {
            for (int i = 0; i < NX; i++) {
                double x = (i + 0.5 - NX / 2.0) * m->dx;
                double y = (j + 0.5 - NY / 2.0) * m->dx;
                double z = (k + 0.5 - NZ / 2.0) * m->dx;
                size_t q = cell_index(i, j, k);
                m->shape[q] = 0.0;
                if (x * x + y * y + z * z <= r2) {
                    nsphere++;
                }
                m->nbnd[q] = (unsigned char)((i == 0) + (i == NX - 1) + (j == 0) + (j == NY - 1)
                                           + (k == 0) + (k == NZ - 1));
            }
        }
    }
    if (nsphere == 0) {
        return;
    }
    double cell_volume = m->dx * m->dx * m->dx;
    double per_watt = 1.0 / ((double)nsphere * cell_volume);
    for (int k = 0; k < NZ; k++) {
        for (int j = 0; j < NY; j++) {
            for (int i = 0; i < NX; i++) {
                double x = (i + 0.5 - NX / 2.0) * m->dx;
                double y = (j + 0.5 - NY / 2.0) * m->dx;
                double z = (k + 0.5 - NZ / 2.0) * m->dx;
                if (x * x + y * y + z * z <= r2) {
                    m->shape[cell_index(i, j, k)] = per_watt;
                }
            }
        }
    }
}

static void set_defaults(Model *m) {
    m->rho = 1078.8;
    m->c = 3540.2;
    m->k = 0.519;
    m->wb = 16.24;
    m->cb = 3617.0;
    m->Ta = 310.15;
    m->Qmet = 10712.9;
    m->dx = 1.0e-3;
    m->rapp = 3.0e-3;
    m->Tinit = 310.15;
    m->Pabl = 0.0;
    m->hbc = 0.0;
    m->Tenv = 310.15;
}

static void reset_fields(Model *m) {
    for (size_t q = 0; q < NCELL; q++) {
        m->T[q] = m->Tinit;
        m->cem[q] = 0.0;
    }
    m->t = 0.0;
    compute_outputs(m);
}

static void step_once(Model *m) {
    const double dt = SOLVER_DT;
    const double inv_rc = 1.0 / (m->rho * m->c);
    const double cf = (m->k * inv_rc) / (m->dx * m->dx);
    const double wf = m->wb * m->cb * inv_rc;
    const double hf = m->hbc * inv_rc / m->dx;
    const double qf = m->Qmet * inv_rc;
    const double pf = m->Pabl * inv_rc;
    const double cem_dt = dt / 60.0;

    for (int k = 0; k < NZ; k++) {
        for (int j = 0; j < NY; j++) {
            for (int i = 0; i < NX; i++) {
                size_t q = cell_index(i, j, k);
                double ti = m->T[q];
                double lap = 0.0;
                if (i > 0) lap += m->T[q - 1] - ti;
                if (i < NX - 1) lap += m->T[q + 1] - ti;
                if (j > 0) lap += m->T[q - NX] - ti;
                if (j < NY - 1) lap += m->T[q + NX] - ti;
                if (k > 0) lap += m->T[q - NX * NY] - ti;
                if (k < NZ - 1) lap += m->T[q + NX * NY] - ti;

                double dtdt = cf * lap
                            + wf * (m->Ta - ti)
                            + hf * (double)m->nbnd[q] * (m->Tenv - ti)
                            + qf
                            + pf * m->shape[q];
                m->Tn[q] = ti + dt * dtdt;

                double tc = ti - KELVIN_OFFSET;
                double r = (tc >= CEM43_T_BREAK_C) ? CEM43_R_HOT : CEM43_R_COLD;
                m->cem[q] += cem_dt * pow(r, CEM43_T_BREAK_C - tc);
            }
        }
    }

    double *swap = m->T;
    m->T = m->Tn;
    m->Tn = swap;
    m->t += dt;
    compute_outputs(m);
}

static fmi3Status init_fields(Model *m, fmi3Float64 start_time) {
    if (!params_valid(m)) {
        log_msg(m, fmi3Error, "invalid parameter value");
        return fmi3Error;
    }
    build_geometry(m);
    int any_source = 0;
    for (size_t q = 0; q < NCELL; q++) {
        if (m->shape[q] > 0.0) any_source = 1;
    }
    if (!any_source) {
        log_msg(m, fmi3Error, "applicator radius is smaller than one grid cell");
        return fmi3Error;
    }
    reset_fields(m);
    m->t = start_time;
    if (!stability_ok(m)) {
        log_msg(m, fmi3Error, "explicit stability bound violated at the current parameters");
        return fmi3Error;
    }
    return fmi3OK;
}

/* FMI 3.0 Common Functions */

const char *fmi3GetVersion(void) {
    return fmi3Version;
}

fmi3Status fmi3SetDebugLogging(fmi3Instance instance, fmi3Boolean loggingOn,
                               size_t nCategories, const fmi3String categories[]) {
    Model *m = (Model *)instance;
    (void)nCategories;
    (void)categories;
    if (!m) return fmi3Error;
    m->loggingOn = loggingOn;
    return fmi3OK;
}

fmi3Instance fmi3InstantiateCoSimulation(fmi3String instanceName, fmi3String instantiationToken,
                                         fmi3String resourcePath, fmi3Boolean visible,
                                         fmi3Boolean loggingOn, fmi3Boolean eventModeUsed,
                                         fmi3Boolean earlyReturnAllowed,
                                         const fmi3ValueReference requiredIntermediateVariables[],
                                         size_t nRequiredIntermediateVariables,
                                         fmi3InstanceEnvironment instanceEnvironment,
                                         fmi3LogMessageCallback logMessage,
                                         fmi3IntermediateUpdateCallback intermediateUpdate) {
    (void)instanceName;
    (void)resourcePath;
    (void)visible;
    (void)eventModeUsed;
    (void)earlyReturnAllowed;
    (void)requiredIntermediateVariables;
    (void)nRequiredIntermediateVariables;
    (void)intermediateUpdate;

    if (!instantiationToken || strcmp(instantiationToken, GUID_TOKEN) != 0) {
        return NULL;
    }

    Model *m = (Model *)calloc(1, sizeof(Model));
    if (!m) return NULL;

    m->env = instanceEnvironment;
    m->logMessage = logMessage;
    m->loggingOn = loggingOn;
    m->state = STATE_CONFIG;
    m->T = m->bufA;
    m->Tn = m->bufB;
    set_defaults(m);
    reset_fields(m);
    return (fmi3Instance)m;
}

void fmi3FreeInstance(fmi3Instance instance) {
    free(instance);
}

/* FMI 3.0 Initialization */

fmi3Status fmi3EnterInitializationMode(fmi3Instance instance, fmi3Boolean toleranceDefined,
                                       fmi3Float64 tolerance, fmi3Float64 startTime,
                                       fmi3Boolean stopTimeDefined, fmi3Float64 stopTime) {
    Model *m = (Model *)instance;
    (void)toleranceDefined;
    (void)tolerance;
    (void)stopTimeDefined;
    (void)stopTime;
    if (!m || m->state != STATE_CONFIG) return fmi3Error;
    m->t = startTime;
    m->state = STATE_INIT;
    return fmi3OK;
}

fmi3Status fmi3ExitInitializationMode(fmi3Instance instance) {
    Model *m = (Model *)instance;
    if (!m || m->state != STATE_INIT) return fmi3Error;
    fmi3Status status = init_fields(m, m->t);
    if (status != fmi3OK) return status;
    m->state = STATE_STEPPING;
    return fmi3OK;
}

fmi3Status fmi3Terminate(fmi3Instance instance) {
    Model *m = (Model *)instance;
    if (!m) return fmi3Error;
    m->state = STATE_TERMINATED;
    return fmi3OK;
}

fmi3Status fmi3Reset(fmi3Instance instance) {
    Model *m = (Model *)instance;
    if (!m) return fmi3Error;
    m->state = STATE_CONFIG;
    set_defaults(m);
    reset_fields(m);
    return fmi3OK;
}

/* FMI 3.0 Co-Simulation */

fmi3Status fmi3DoStep(fmi3Instance instance, fmi3Float64 currentCommunicationPoint,
                      fmi3Float64 communicationStepSize, fmi3Boolean noSetFMUStatePriorToCurrentPoint,
                      fmi3Boolean *eventHandlingNeeded, fmi3Boolean *terminateSimulation,
                      fmi3Boolean *earlyReturn, fmi3Float64 *lastSuccessfulTime) {
    Model *m = (Model *)instance;
    (void)noSetFMUStatePriorToCurrentPoint;
    if (!m || m->state != STATE_STEPPING) return fmi3Error;

    if (fabs(communicationStepSize - SOLVER_DT) > 1.0e-12) {
        log_msg(m, fmi3Error, "communicationStepSize must equal the solver step (0.1 s)");
        return fmi3Error;
    }
    if (fabs(currentCommunicationPoint - m->t) > 1.0e-9) {
        log_msg(m, fmi3Error, "currentCommunicationPoint does not match the FMU time");
        return fmi3Error;
    }
    if (!stability_ok(m)) {
        log_msg(m, fmi3Error, "explicit stability bound violated at the current boundary input");
        return fmi3Error;
    }

    step_once(m);

    if (eventHandlingNeeded) *eventHandlingNeeded = fmi3False;
    if (terminateSimulation) *terminateSimulation = fmi3False;
    if (earlyReturn) *earlyReturn = fmi3False;
    if (lastSuccessfulTime) *lastSuccessfulTime = m->t;
    return fmi3OK;
}

/* FMI 3.0 Getting and setting variable values */

fmi3Status fmi3GetFloat64(fmi3Instance instance, const fmi3ValueReference valueReferences[],
                          size_t nValueReferences, fmi3Float64 values[], size_t nValues) {
    Model *m = (Model *)instance;
    if (!m || nValues != nValueReferences) return fmi3Error;
    for (size_t n = 0; n < nValueReferences; n++) {
        switch (valueReferences[n]) {
            case VR_TIME: values[n] = m->t; break;
            case VR_RHO: values[n] = m->rho; break;
            case VR_C: values[n] = m->c; break;
            case VR_K: values[n] = m->k; break;
            case VR_WB: values[n] = m->wb; break;
            case VR_CB: values[n] = m->cb; break;
            case VR_TA: values[n] = m->Ta; break;
            case VR_QMET: values[n] = m->Qmet; break;
            case VR_DX: values[n] = m->dx; break;
            case VR_RAPP: values[n] = m->rapp; break;
            case VR_TINIT: values[n] = m->Tinit; break;
            case VR_PABL: values[n] = m->Pabl; break;
            case VR_HBC: values[n] = m->hbc; break;
            case VR_TENV: values[n] = m->Tenv; break;
            case VR_TMAX: values[n] = m->Tmax; break;
            case VR_TMEAN: values[n] = m->Tmean; break;
            case VR_V60: values[n] = m->V60; break;
            case VR_VLES: values[n] = m->Vles; break;
            default: return fmi3Error;
        }
    }
    return fmi3OK;
}

fmi3Status fmi3SetFloat64(fmi3Instance instance, const fmi3ValueReference valueReferences[],
                          size_t nValueReferences, const fmi3Float64 values[], size_t nValues) {
    Model *m = (Model *)instance;
    if (!m || nValues != nValueReferences || m->state == STATE_TERMINATED) return fmi3Error;
    for (size_t n = 0; n < nValueReferences; n++) {
        fmi3ValueReference vr = valueReferences[n];
        fmi3Float64 v = values[n];
        int is_parameter = vr >= VR_RHO && vr <= VR_TINIT;
        if (is_parameter && m->state != STATE_CONFIG && m->state != STATE_INIT) {
            log_msg(m, fmi3Error, "fixed parameters can be set only before initialization");
            return fmi3Error;
        }
        switch (vr) {
            case VR_RHO: m->rho = v; break;
            case VR_C: m->c = v; break;
            case VR_K: m->k = v; break;
            case VR_WB: m->wb = v; break;
            case VR_CB: m->cb = v; break;
            case VR_TA: m->Ta = v; break;
            case VR_QMET: m->Qmet = v; break;
            case VR_DX: m->dx = v; break;
            case VR_RAPP: m->rapp = v; break;
            case VR_TINIT: m->Tinit = v; break;
            case VR_PABL: m->Pabl = v; break;
            case VR_HBC: m->hbc = v; break;
            case VR_TENV: m->Tenv = v; break;
            default: return fmi3Error;
        }
    }
    return fmi3OK;
}
