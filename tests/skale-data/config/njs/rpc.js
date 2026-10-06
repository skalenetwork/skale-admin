// Per-chain JSON-RPC limits on top of limit_req: batch weight, bans, heavy methods, gating.
// The chain server sets rpc_chain, rpc_class and the limits; peers never reach this handler.

const GATED_METHODS = [
    'skale_getSnapshot',
    'skale_downloadSnapshotFragment',
    'skale_getSnapshotSignature',
    'skale_shutdownInstance',
];
const GATED_PREFIXES = ['debug_', 'admin_', 'personal_', 'miner_', 'skale_performanceTracking'];
const HEAVY_METHODS = ['eth_getLogs', 'eth_call', 'eth_estimateGas'];
const HEAVY_PREFIXES = ['debug_'];
const HOP_BY_HOP = ['connection', 'keep-alive', 'transfer-encoding', 'content-length'];

function matches(method, names, prefixes) {
    return names.includes(method) || prefixes.some((prefix) => method.startsWith(prefix));
}

function limit(r, name) {
    return Number(r.variables[name]);
}

function exceeded(r, key, weight, name) {
    return ngx.shared.rpc_counters.incr(key, weight, 0) > limit(r, name);
}

function reject(r, status, id, code, message) {
    r.headersOut['Content-Type'] = 'application/json';
    r.headersOut['Access-Control-Allow-Origin'] = '*';
    if (status === 429) {
        r.headersOut['Retry-After'] = '1';
    }
    const error = { jsonrpc: '2.0', id: id === undefined ? null : id, error: { code: code, message: message } };
    r.return(status, JSON.stringify(error));
}

async function relay(r, options) {
    const reply = await r.subrequest('/_upstream', options);
    for (const name in reply.headersOut) {
        if (!HOP_BY_HOP.includes(name.toLowerCase())) {
            r.headersOut[name] = reply.headersOut[name];
        }
    }
    r.return(reply.status, reply.responseBuffer);
}

// Returns true when the public client is over a limit; over a per-client limit also bans it.
function limited(r, weight, heavy) {
    const now = Math.floor(Date.now() / 1000);
    const minute = Math.floor(now / 60);
    const chain = r.variables.rpc_chain;
    const client = `${chain}:${r.remoteAddress}`;
    const bans = ngx.shared.rpc_bans;

    if ((bans.get(client) || 0) > now) {
        return true;
    }
    // the chain-wide cap rejects without banning anyone, skaled's own global limit backs it up
    if (
        exceeded(r, `${chain}:*:s:${now}`, weight, 'rpc_global_rps') ||
        exceeded(r, `${chain}:*:m:${minute}`, weight, 'rpc_global_rpm')
    ) {
        return true;
    }
    let seconds = 0;
    if (exceeded(r, `${client}:s:${now}`, weight, 'rpc_client_rps')) {
        seconds = limit(r, 'rpc_ban_short');
    } else if (exceeded(r, `${client}:m:${minute}`, weight, 'rpc_client_rpm')) {
        seconds = limit(r, 'rpc_ban_long');
    } else if (heavy > 0 && exceeded(r, `${client}:h:${now}`, heavy, 'rpc_heavy_rps')) {
        seconds = limit(r, 'rpc_ban_short');
    }
    if (seconds > 0) {
        bans.set(client, now + seconds);
        return true;
    }
    return false;
}

async function handle(r) {
    if (r.method !== 'POST') {
        // CORS preflight and anything else skaled answers itself
        return relay(r, { method: r.method });
    }

    let body;
    try {
        body = JSON.parse(r.requestText);
    } catch (e) {
        return reject(r, 400, null, -32700, 'parse error');
    }
    const calls = Array.isArray(body) ? body : [body];
    if (calls.length === 0 || calls.length > limit(r, 'rpc_max_batch')) {
        return reject(r, 400, null, -32600, 'invalid batch size');
    }

    let heavy = 0;
    for (let i = 0; i < calls.length; i++) {
        const call = calls[i];
        const method = call && typeof call.method === 'string' ? call.method : '';
        if (matches(method, GATED_METHODS, GATED_PREFIXES)) {
            return reject(r, 403, call.id, -32601, 'method not allowed');
        }
        if (matches(method, HEAVY_METHODS, HEAVY_PREFIXES)) {
            heavy += 1;
        }
    }

    if (r.variables.rpc_class === 'public' && limited(r, calls.length, heavy)) {
        return reject(r, 429, null, -32005, 'rate limited');
    }

    return relay(r, { method: 'POST', body: r.requestText });
}

export default { handle: handle };
