import { useState, useEffect, useCallback } from 'react';

/**
 * Generic hook for fetching data from the backend API.
 * Returns { data, loading, error, refetch }
 *
 * @param {Function} apiFn  – async function that returns data (from services/api.js)
 * @param {Array}    deps   – dependency array for re-fetching
 * @param {*}        initial – initial state for data (default [])
 */
export function useAPI(apiFn, deps = [], initial = []) {
    const [data, setData] = useState(initial);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchData = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const result = await apiFn();
            setData(result);
        } catch (err) {
            setError(err.message);
            console.warn('API fetch failed, using fallback:', err.message);
        } finally {
            setLoading(false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, deps);

    useEffect(() => { fetchData(); }, [fetchData]);

    return { data, loading, error, refetch: fetchData };
}
