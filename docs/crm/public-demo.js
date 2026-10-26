"use strict";
// Public browser-local demo: no API, session, credentials or external requests.
window.RPRegistry={status:'demo',rows:[],refresh(){window.dispatchEvent(new Event('rp-registry'));}};
