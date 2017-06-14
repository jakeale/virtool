/**
 *
 *
 * @copyright 2017 Government of Canada
 * @license MIT
 * @author igboyes
 *
 */

import { call, put, takeEvery, takeLatest } from "redux-saga/effects";

import jobsAPI from "./api";
import { setPending } from "../wrappers";
import { FIND_JOBS, GET_JOB, REMOVE_JOB, TEST_JOB, GET_RESOURCES }  from "../actionTypes";

export function* watchJobs () {
    yield takeLatest(FIND_JOBS.REQUESTED, findJobs);
    yield takeLatest(GET_JOB.REQUESTED, getJob);
    yield takeEvery(REMOVE_JOB.REQUESTED, removeJob);
    yield takeLatest(TEST_JOB.REQUESTED, testJob);
    yield takeLatest(GET_RESOURCES.REQUESTED, getResources);
}

export function* findJobs (action) {
    yield setPending(bgFindJobs, action);
}

export function* bgFindJobs (action) {
    try {
        const response = yield call(jobsAPI.find);
        yield put({type: FIND_JOBS.SUCCEEDED, data: response.body});
    } catch (error) {
        yield put({type: FIND_JOBS.FAILED}, error);
    }
}

export function* getJob (action) {
    yield setPending(function* () {
        try {
            const response = yield call(jobsAPI.get, action.jobId);
            yield put({type: GET_JOB.SUCCEEDED, data: response.body});
        } catch (error) {
            yield put({type: GET_JOB.FAILED}, error);
        }
    }, action);
}

export function* removeJob (action) {
    yield setPending(function* () {
        try {
            yield call(jobsAPI.remove, action.jobId);
            yield put({type: REMOVE_JOB.SUCCEEDED, jobId: action.jobId});
        } catch (error) {
            yield put({type: REMOVE_JOB.FAILED}, error);
        }
    }, action);
}

export function* testJob (action) {
    try {
        const response = yield call(jobsAPI.test, action);
        yield put({type: TEST_JOB.SUCCEEDED, data: response.body});
    } catch (error) {
        yield put({type: TEST_JOB.FAILED}, error);
    }
}

export function* getResources (action) {
    try {
        const response = yield call(jobsAPI.getResources, action);
        yield put({type: GET_RESOURCES.SUCCEEDED, data: response.body});
    } catch (error) {
        yield put({type: GET_RESOURCES.FAILED}, error);
    }
}
