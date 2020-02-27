import Fuse from "fuse.js";
import { get, find, intersection, map, reject, sortBy, toNumber, toString, keyBy } from "lodash-es";
import { createSelector } from "reselect";
import createCachedSelector from "re-reselect";
import { getMaxReadLength } from "../samples/selectors";

const getReadCount = state => state.analyses.detail.read_count;

export const getActiveId = state => state.analyses.activeId;

export const getAlgorithm = state => state.analyses.detail.algorithm;

export const getAnalysisDetailId = state => get(state, "analyses.detail.id", null);

export const getResults = state => state.analyses.detail.results;

export const getMaxSequenceLength = state => state.analyses.detail.maxSequenceLength;

export const getFuse = createSelector([getAlgorithm, getResults], (algorithm, results) => {
    let keys = ["name", "abbreviation"];

    if (algorithm === "nuvs") {
        keys = ["families", "names"];
    }

    return new Fuse(results, {
        keys,
        id: "id",
        minMatchCharLength: 2,
        threshold: 0.3,
        tokenize: true
    });
});

export const getFilterOTUs = state => state.analyses.filterOTUs;
export const getFilterSequences = state => state.analyses.filterSequences;

export const getFilterIds = createSelector(
    [getAlgorithm, getResults, getFilterOTUs, getFilterSequences, getMaxReadLength, getReadCount],
    (algorithm, results, filterOTUs, filterSequences, maxReadLength, readCount) => {
        if (algorithm === "nuvs") {
            const filteredResults = filterSequences ? reject(results, { e: undefined }) : results;
            return map(filteredResults, "id");
        }

        if (algorithm === "pathoscope_bowtie" && filterOTUs) {
            const filteredResults = reject(results, hit => {
                return hit.pi * readCount < (hit.length * 0.8) / maxReadLength;
            });
            return map(filteredResults, "id");
        }

        // const filteredResults = filterOTUs ? reject(results, { : undefined }) : results;
        return map(results, "id");
    }
);

export const getSearchIds = state => state.analyses.searchIds;

export const getSortKey = state => state.analyses.sortKey;

export const getSortIds = createSelector([getAlgorithm, getResults, getSortKey], (algorithm, results, sortKey) => {
    if (sortKey === "e") {
        return map(sortBy(results, "e"), "id");
    }
    if (sortKey === "orfs") {
        return map(sortBy(results, "annotatedOrfCount").reverse(), "id");
    }

    if (sortKey === "length") {
        return map(sortBy(results, "sequence.length").reverse(), "id");
    }

    if (sortKey === "depth") {
        return map(sortBy(results, "depth"), "id");
    }

    if (sortKey === "coverage") {
        return map(sortBy(results, "coverage").reverse(), "id");
    }

    if (sortKey === "weight") {
        return map(sortBy(results, "pi"), "id");
    }

    return map(results, "id");
});

export const getMatches = createSelector(
    [getAlgorithm, getResults, getFilterIds, getSearchIds, getSortIds],
    (algorithm, results, filterIds, searchIds, sortIds) => {
        let matchIds;

        if (searchIds) {
            matchIds = intersection(sortIds, filterIds, map(searchIds, algorithm === "nuvs" ? toNumber : toString));
        } else {
            matchIds = intersection(sortIds, filterIds);
        }

        const keyed = keyBy(results, "id");

        return map(matchIds, id => keyed[id]);
    }
);

export const getActiveHit = createSelector([getAlgorithm, getMatches, getActiveId], (algorithm, matches, activeId) => {
    if (activeId !== null) {
        const hit = find(matches, { id: activeId });

        if (hit) {
            return hit;
        }
    }

    return matches[0] || null;
});

const getItemId = (state, itemId) => itemId;

export const getPathoscopeItem = createCachedSelector([getResults, getItemId], (results, id) => find(results, { id }))(
    (state, itemId) => itemId
);
