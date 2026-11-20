/**
 * fuel-prices-card v3 – kuro kainų kortelės (kk2.png / kk3.png stilius).
 *
 * Duomenų šaltinis: VIENAS sensorius su visų degalinių JSON atribute
 * (sensor.marijampole_degalines → stations, fuel_names).
 *
 * Režimai:
 *   summary – kuro rūšies suvestinė: spalvotas ženklelis su trumpiniu,
 *             kuro pavadinimas (iš puslapio), pigiausia kaina, degalinė, vidurkis
 *   station – degalinė: logotipas (auto iš prekės ženklo),
 *             pavadinimas, adresas, kuro žetonai (su „—" slepiami)
 *
 * Redaktorius:
 *   - įkeliant naują kortelę pirmiausia siūlomas REŽIMO pasirinkimas (plytelės),
 *     po pasirinkimo rodomi tik to režimo laukai (režimo keisti negalima);
 *   - subjektas rodomas kaip tile kortelėje, bet nekeičiamas (read-only);
 *   - degalinės režime: „Rodyti logotipą" perjungiklis ir žetonų matomumo
 *     perjungikliai (benzinas / dyzelinas / dujos).
 */

const STYLE = `
  <style>
    ha-card { height: 100%; overflow: hidden; }
    .fp-body {
      padding: 4px 14px; height: 100%; box-sizing: border-box;
      display: flex; flex-direction: column; justify-content: center;
      position: relative;
    }
    .fp-empty { font-size: 13px; color: var(--secondary-text-color); }

    /* Šaltinio nuoroda ir neoficialumo žyma – visada matomos kortelėje */
    .fp-attrib {
      margin-top: auto; padding-top: 2px;
      border-top: 1px solid var(--divider-color, rgba(128,128,128,.18));
      font-size: 8px; line-height: 1.1; color: var(--secondary-text-color);
    }
    .fp-attrib-src {
      display: flex; align-items: center; gap: 2px; white-space: nowrap;
    }
    .fp-attrib-status {
      margin-top: 0; font-weight: 400; letter-spacing: .1px;
    }
    .fp-attrib-one {
      display: flex; align-items: center; gap: 2px; white-space: nowrap;
    }
    .fp-attrib-one .fp-attrib-status-inline { font-weight: 400; }
    .fp-attrib a { color: inherit; text-decoration: none; }
    .fp-attrib a:hover { text-decoration: underline; }
    .fp-attrib b { font-weight: 400; color: var(--secondary-text-color); }

    .fp-head { display: flex; align-items: center; gap: 10px; }
    .fp-badge {
      width: 28px; height: 28px; border-radius: 8px; flex: none;
      display: flex; align-items: center; justify-content: center;
      font-size: 11px; font-weight: 700; color: #fff;
    }
    .fp-title { font-size: 15px; font-weight: 700; color: var(--primary-text-color); }

    .fp-price { font-size: 19px; font-weight: 700; line-height: 1.1; color: var(--primary-text-color); margin-top: 2px; }
    .fp-divider { border-top: 1px solid var(--divider-color, rgba(128,128,128,.25)); margin: 2px 0 1px; }

    .fp-row { display: flex; align-items: center; gap: 8px; font-size: 13px; line-height: 1.15; color: var(--secondary-text-color); margin-top: 0; }
    .fp-row + .fp-row { margin-top: 2px; }
    .fp-row-average { font-size: 11px; }
    .fp-row ha-icon { --mdc-icon-size: 16px; flex: none; }
    .fp-row b { color: var(--primary-text-color); font-weight: 600; }

    .fp-header { display: flex; align-items: center; gap: 10px; }
    .fp-logo-frame {
      width: 44px; height: 44px; flex: none;
      display: flex; align-items: center; justify-content: center;
    }
    .fp-logo { max-width: 40px; max-height: 40px; object-fit: contain; }
    .fp-name { font-size: 17px; font-weight: 700; color: var(--primary-text-color); }
    .fp-addr {
      display: flex; align-items: center; gap: 4px; margin-top: 1px;
      font-size: 11px; color: var(--secondary-text-color);
    }
    .fp-addr ha-icon { --mdc-icon-size: 13px; }

    .fp-chips { display: grid; grid-template-columns: repeat(auto-fit, minmax(96px, 1fr)); gap: 6px; margin-top: 4px; }
    .fp-chip {
      background: var(--secondary-background-color, rgba(128, 128, 128, .12));
      border-radius: var(--ha-card-border-radius, 12px);
      padding: 6px 8px;
    }
    .fp-chip .fp-label {
      font-size: 10px; font-weight: 600; letter-spacing: .5px;
      text-transform: uppercase; color: var(--secondary-text-color);
    }
    .fp-chip .fp-price { font-size: 14px; font-weight: 700; margin-top: 0; color: var(--primary-text-color); }
  </style>
`;

// Kuro rūšys: trumpinis ženkleliui, spalva (temos kintamasis).
// Pavadinimai – iš puslapio (fuel_names attribute arba FUEL_DISPLAY atsarginė).
const FUEL_META = {
  "95":        { short: "95",  bg: "var(--success-color)" },
  "98":        { short: "98",  bg: "var(--info-color)" },
  "Dyzelinas": { short: "D",   bg: "#1b1b1b" },
  "Dujos":     { short: "LPG", bg: "var(--warning-color)" }
};
const fuelMeta = label => FUEL_META[label] || { short: (label || "?").slice(0, 3), bg: "var(--primary-color)" };

const FUEL_DISPLAY = { "95": "95 benzinas", "98": "98 benzinas", "Dyzelinas": "Dyzelinas", "Dujos": "LPG dujos" };

const DEFAULT_ENTITY = "sensor.marijampole_degalines";

// Kortelės failai patiekti integracijos statiniu keliu.
const ASSET_BASE = "/lt_fuel_prices";

// Duomenų šaltinio formuluotė ir atsakomybės paaiškinimas (LEA reikalavimas).
const ATTRIBUTION_TITLE =
  "Duomenų šaltinis – Lietuvos energetikos agentūra (LEA), https://degalukainos.ena.lt/. " +
  "Pirminiai degalų kainų duomenų teikėjai – degalines valdančios įmonės. " +
  "Neoficiali trečiosios šalies integracija. " +
  "Tai nepriklausoma trečiosios šalies sukurta integracija. " +
  "Už jos veikimą, duomenų nuskaitymą, atnaujinimą ir atvaizdavimą " +
  "integracijoje atsako jos kūrėjas. " +
  "LEA šios integracijos nekuria ir neadministruoja.";
const attribution = (oneLine = false) => {
  const source =
    `<span>Duomenų šaltinis – <b>LEA</b></span><span>·</span>` +
    `<a href="https://degalukainos.ena.lt/" target="_blank" rel="noopener noreferrer">degalukainos.ena.lt</a>`;
  if (oneLine) {
    return (
      `<div class="fp-attrib fp-attrib-one" title="${ATTRIBUTION_TITLE}">` +
      source +
      `<span>·</span>` +
      `<span class="fp-attrib-status-inline">Neoficiali trečiosios šalies integracija</span>` +
      `</div>`
    );
  }
  return (
    `<div class="fp-attrib" title="${ATTRIBUTION_TITLE}">` +
    `<div class="fp-attrib-src">${source}</div>` +
    `<div class="fp-attrib-status">Neoficiali trečiosios šalies integracija</div>` +
    `</div>`
  );
};

// Ženklas -> lokalus logotipo failas (integracai logotipų nebeduoda).
const LOGO_FILES = {
  "neste": "neste.png",
  "emsi": "emsi.png",
  "circle k": "circlek.png",
  "baltic petroleum": "balticpetroleum.png",
  "alauša": "alausa.png",
  "alausa": "alausa.png",
  "viada": "viada.png",
  "saurida": "saurida.png"
};
const DEFAULT_LOGO = "default.png";

// Benzinas apima 95 (ir 98, jei kada atsirastų), Dyzelinas ir Dujos atskirai.
const fuelGroup = label =>
  label === "95" || label === "98" ? "petrol"
  : label === "Dyzelinas" ? "diesel"
  : label === "Dujos" ? "lpg"
  : "other";

const parsePrice = v => {
  if (!v || v === "—" || v === "unknown" || v === "unavailable") return null;
  const n = Number(String(v).replace("€", "").replace(",", ".").trim());
  return isNaN(n) ? null : n;
};

class FuelPricesCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.data_entity) {
      throw new Error("fuel-prices-card: nurodykite data_entity");
    }
    if (config.mode && !["summary", "station"].includes(config.mode)) {
      throw new Error("fuel-prices-card: režimas turi būti summary arba station");
    }
    if (config.mode === "station" && !config.station) {
      throw new Error("fuel-prices-card: station režimui reikia station (Prekės ženklas - adresas)");
    }
    this._config = config;
    // Svarbu: persipiešiame ir pakeitus konfigūraciją (HA peržiūroje hass
    // gali nesikeisti, tad be šito kortelė rodytų SENĄ turinį).
    this._refresh();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.isConnected) return;
    this._refresh();
  }

  _refresh() {
    const sig = this._signature();
    if (sig === this._lastSig) return;
    this._lastSig = sig;
    this._update();
  }

  // multiscrape (parse_result=True) atributus atiduoda jau suparsuotus
  // (masyvą/objektą), senesnės versijos – JSON stringą. Priimame abu.
  _jsonAttr(value, fallback) {
    if (value === undefined || value === null) return fallback;
    if (typeof value !== "string") return value;
    try { return JSON.parse(value); } catch { return fallback; }
  }

  _stations() {
    const attrs = this._hass?.states?.[this._config.data_entity]?.attributes;
    return this._jsonAttr(attrs?.stations, []);
  }

  _fuelNames() {
    const attrs = this._hass?.states?.[this._config.data_entity]?.attributes;
    return this._jsonAttr(attrs?.fuel_names, {});
  }

  _signature() {
    const c = this._config;
    if (!this._hass) return "";
    const attrs = this._hass.states[c.data_entity]?.attributes;
    // JSON.stringify būtina: masyvui `${attrs.stations}` visada duotų
    // "[object Object]" ir kortelė nepersipieštų pasikeitus kainoms.
    return `${JSON.stringify(attrs?.stations ?? "")}|${JSON.stringify(attrs?.fuel_names ?? "")}|${c.data_entity || ""}|${c.mode || ""}|${c.fuel || ""}|${c.station || ""}|${c.show_logo}|${c.show_petrol}|${c.show_diesel}|${c.show_lpg}`;
  }

  // Logotipas: pirmiausia iš duomenų (jei duotas), kitu atveju pagal ženklą.
  _logoSrc(s) {
    if (s && s.logo && s.logo.url) {
      const url = String(s.logo.url);
      return /^(https?:)?\//.test(url)
        ? url
        : `${ASSET_BASE}/logos/${url.split("/").pop().split("?")[0]}`;
    }
    if (!s || !s.brand) return null;
    const brand = String(s.brand).toLowerCase();
    for (const [prefix, file] of Object.entries(LOGO_FILES)) {
      if (brand.includes(prefix)) {
        return `${ASSET_BASE}/logos/${file}`;
      }
    }
    return `${ASSET_BASE}/logos/${DEFAULT_LOGO}`;
  }

  _update() {
    const c = this._config;
    const stations = this._stations();
    const fuelNames = this._fuelNames();
    let body = "";

    if (!c.mode) {
      body = `<div class="fp-empty">Atidarykite kortelės nustatymus ir pasirinkite režimą.</div>`;
    } else if (c.mode === "summary") {
      const fuel = c.fuel || "95";
      const meta = fuelMeta(fuel);
      const name = fuelNames[fuel] || FUEL_DISPLAY[fuel] || fuel;

      const values = [];
      let cheapest = null;
      for (const s of stations) {
        const p = (s.prices || []).find(x => x.label === fuel);
        const n = parsePrice(p?.value);
        if (n !== null) {
          values.push(n);
          if (!cheapest || n < cheapest.price) cheapest = { price: n, brand: s.brand };
        }
      }
      const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
      const fmtP = n => n === null ? "—" : n.toFixed(3).replace(".", ",") + " €";
      const noData = values.length === 0;

      body = `
        <div class="fp-head">
          <div class="fp-badge" style="background: ${meta.bg}; color: #fff;">${meta.short}</div>
          <div class="fp-title">${name}</div>
        </div>
        <div class="fp-price">${fmtP(cheapest ? cheapest.price : null)}</div>
        <div class="fp-divider"></div>
        ${noData
          ? `<div class="fp-row"><ha-icon icon="mdi:database-alert"></ha-icon><span>LEA šiuo metu neskelbia kainų</span></div>`
          : `<div class="fp-row"><span>Pigiausia – <b>${cheapest.brand}</b></span></div>
             <div class="fp-row fp-row-average"><span>Vidutiniškai <b>${fmtP(avg)}</b></span></div>`}`;
    } else {
      const key = c.station || "";
      const s = stations.find(x => `${x.brand} - ${x.address}` === key);
      const showLogo = c.show_logo !== false;

      let logoHtml = "";
      if (showLogo) {
        const src = this._logoSrc(s);
        logoHtml = src
          ? `<div class="fp-logo-frame"><img class="fp-logo" src="${src}" alt=""></div>`
          : `<div class="fp-logo-frame"><ha-icon icon="mdi:local-gas-station" style="color: var(--secondary-text-color);"></ha-icon></div>`;
      }

      const name = s ? s.brand : (key.split(" - ")[0] || "—");
      const visible = g => g === "petrol" ? c.show_petrol !== false
        : g === "diesel" ? c.show_diesel !== false
        : g === "lpg" ? c.show_lpg !== false
        : true;

      const stationPrices = (s && s.prices) || [];
      const hasAnyPrice = stationPrices.some(
        p => p.value && p.value !== "—" && p.value !== "unknown" && p.value !== "unavailable"
      );
      const chips = hasAnyPrice
        ? stationPrices
            .filter(p => p.value && p.value !== "—" && p.value !== "unknown" && visible(fuelGroup(p.label)))
            .map(p => {
              const lbl = fuelNames[p.label] || FUEL_DISPLAY[p.label] || p.label;
              return `<div class="fp-chip"><div class="fp-label">${lbl}</div><div class="fp-price">${p.value}</div></div>`;
            })
            .join("")
        : "";
      const chipsHtml = hasAnyPrice
        ? `<div class="fp-chips">${chips}</div>`
        : (s
            ? `<div class="fp-row"><ha-icon icon="mdi:database-alert"></ha-icon><span>LEA šiuo metu neskelbia kainų</span></div>`
            : "");

      body = `
        <div class="fp-header">
          ${logoHtml}
          <div>
            <div class="fp-name">${name}</div>
            ${s ? `<div class="fp-addr"><ha-icon icon="mdi:map-marker"></ha-icon><span>${s.address}</span></div>` : ""}
          </div>
        </div>
        ${chipsHtml}`;
    }

    this.innerHTML = `${STYLE}<ha-card><div class="fp-body">${body}${attribution(c.mode === "station")}</div></ha-card>`;
  }

  getCardSize() {
    // Abi režimų kortelės – po 2 „plyteles".
    return 2;
  }

  // Sections vaizdo dydžio keitimas (be šio metodo HA rodo įspėjimą
  // „nevisiškai palaiko dydžio keitimą"). Eilutė = 56px + 8px tarpas.
  // Suvestinei užtenka pusės pločio (6 stulpeliai iš 12).
  getGridOptions() {
    const isSummary = this._config && this._config.mode === "summary";
    return isSummary
      ? { columns: 6, min_columns: 2, max_columns: 12, rows: 2, min_rows: 2, max_rows: 8 }
      : { columns: "full", rows: 2, min_rows: 2, max_rows: 8 };
  }

  static getStubConfig() {
    return { type: "custom:fuel-prices-card", data_entity: DEFAULT_ENTITY };
  }

  static getConfigElement() {
    return document.createElement("fuel-prices-card-editor");
  }
}

/* ------------------------------------------------------------------ */
/* Vaizdinis redaktorius (HA native komponentai – kaip tile kortelės) */
/* ------------------------------------------------------------------ */

const EDITOR_STYLE = `
  <style>
    .ed { display: flex; flex-direction: column; gap: 14px; padding: 8px 4px; }
    .ed-label {
      font-size: 12px; letter-spacing: .4px;
      color: var(--secondary-text-color); margin-bottom: 4px;
    }
    .ed-entity {
      display: flex; flex-direction: column; gap: 2px;
      padding: 10px 12px;
      border: 1px solid var(--divider-color, rgba(128,128,128,.3));
      border-radius: var(--ha-card-border-radius, 12px);
    }
    .ed-entity-name { font-size: 14px; color: var(--primary-text-color); }
    .ed-switch-row {
      display: flex; align-items: center; justify-content: space-between;
      gap: 12px; font-size: 14px; color: var(--primary-text-color);
      min-height: 40px;
    }
    .ed-switch-row.is-off { opacity: .5; }
    .ed-choices { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .ed-choice {
      display: flex; flex-direction: column; align-items: center; gap: 8px;
      padding: 20px 12px; cursor: pointer; text-align: center;
      border: 1px solid var(--divider-color, rgba(128,128,128,.3));
      border-radius: 14px;
      color: var(--primary-text-color); font-size: 14px; font-weight: 600;
    }
    .ed-choice:hover { border-color: var(--primary-color); }
    .ed-choice ha-icon { --mdc-icon-size: 28px; }
    .ed-note { font-size: 12px; color: var(--secondary-text-color); }
  </style>
`;

class FuelPricesCardEditor extends HTMLElement {
  setConfig(config) {
    this._applyConfig(config);
  }

  set config(config) {
    this._applyConfig(config);
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    // Persikuriame TIK kai pasikeitė duomenys (stations/fuel_names), o ne kiekviename
    // hass atnaujinime – kitaip iškart užsidaro atidarytas dropdown'as.
    const sig = this._dataSig();
    if (sig !== this._lastDataSig) {
      this._lastDataSig = sig;
      if (this.isConnected) this._render();
    }
  }

  _applyConfig(config) {
    this._config = config;
    if (this._lastEmitted && JSON.stringify(config) === JSON.stringify(this._lastEmitted)) return;
    this._render();
  }

  connectedCallback() {
    if (this._config && !this.innerHTML) this._render();
  }

  _dataSig() {
    const attrs = this._hass?.states?.[this._config?.data_entity]?.attributes;
    return `${JSON.stringify(attrs?.stations ?? "")}|${JSON.stringify(attrs?.fuel_names ?? "")}`;
  }

  _jsonAttr(value, fallback) {
    if (value === undefined || value === null) return fallback;
    if (typeof value !== "string") return value;
    try { return JSON.parse(value); } catch { return fallback; }
  }

  _stations() {
    const attrs = this._hass?.states?.[this._config?.data_entity]?.attributes;
    return this._jsonAttr(attrs?.stations, []);
  }

  _fuelNames() {
    const attrs = this._hass?.states?.[this._config?.data_entity]?.attributes;
    return this._jsonAttr(attrs?.fuel_names, {});
  }

  _entityLabel() {
    const c = this._config || {};
    const st = this._hass?.states?.[c.data_entity || DEFAULT_ENTITY];
    return (st && (st.attributes.friendly_name || st.entity_id)) || (c.data_entity || DEFAULT_ENTITY);
  }

  _render() {
    const c = this._config || {};

    // Nėra režimo (nauja kortelė) – pirmiausia pasirenkamas REŽIMAS.
    if (!c.mode) {
      this.innerHTML = `${EDITOR_STYLE}<div class="ed">
        <div class="ed-label">Režimas</div>
        <div class="ed-choices">
          <div class="ed-choice" id="ed-mode-summary">
            <ha-icon icon="mdi:chart-line"></ha-icon>
            <span>Suvestinė<br>(pigiausia kaina)</span>
          </div>
          <div class="ed-choice" id="ed-mode-station">
            <ha-icon icon="mdi:gas-station"></ha-icon>
            <span>Degalinė<br>(logotipas, žetonai)</span>
          </div>
        </div>
        <div class="ed-note">Pasirinkus režimą, jo keisti nebus galima.</div>
      </div>`;

      const pick = mode => {
        // Išlaikome pradinę konfigūraciją (svarbiausia – "type"), kitaip HA
        // rodo „Konfigūracijos klaida: Nepateiktas joks tipas".
        const base = { ...(this._config || {}) };
        const next = mode === "summary"
          ? { ...base, mode: "summary", data_entity: base.data_entity || DEFAULT_ENTITY, fuel: base.fuel || "95" }
          : {
              ...base, mode: "station", data_entity: base.data_entity || DEFAULT_ENTITY,
              station: base.station || this._defaultStation(),
              show_logo: base.show_logo !== false,
              show_petrol: base.show_petrol !== false,
              show_diesel: base.show_diesel !== false,
              show_lpg: base.show_lpg !== false
            };
        this._config = next;
        this._render();
        this._emit(next);
      };
      this.querySelector("#ed-mode-summary").addEventListener("click", () => pick("summary"));
      this.querySelector("#ed-mode-station").addEventListener("click", () => pick("station"));
      return;
    }

    const isSummary = c.mode === "summary";
    const stations = this._stations();
    const fuelNames = this._fuelNames();

    const fuels = [...new Set(stations.flatMap(s => (s.prices || []).map(p => p.label)))].sort();
    if (!fuels.length) fuels.push("95", "98", "Dyzelinas", "Dujos");

    const stationKeys = stations.map(s => `${s.brand} - ${s.address}`);
    const fuelLabel = f => fuelNames[f] || FUEL_DISPLAY[f] || f;

    const entityRow = `
      <div>
        <div class="ed-label">Subjektas</div>
        <div class="ed-entity"><span class="ed-entity-name">${this._entityLabel()}</span></div>
      </div>`;

    if (isSummary) {
      const fuelItems = fuels.map(f => ({ value: f, label: fuelLabel(f) }));
      this.innerHTML = `${EDITOR_STYLE}<div class="ed">
        ${entityRow}
        <ha-select id="ed-fuel" label="Kuro rūšis"></ha-select>
      </div>`;
      this._setupSelect("#ed-fuel", fuelItems, c.fuel || "95");
    } else {
      const stationItems = stationKeys.length
        ? stationKeys.map(k => ({ value: k, label: k }))
        : [{ value: c.station || "", label: c.station || "(duomenys dar nepakrauti)" }];

      this.innerHTML = `${EDITOR_STYLE}<div class="ed">
        ${entityRow}
        <ha-select id="ed-station" label="Degalinė"></ha-select>
        <div class="ed-switch-row"><span>Rodyti logotipą</span><ha-switch id="ed-logo"></ha-switch></div>
        <div>
          <div class="ed-label">Rodomi žetonai</div>
          <div class="ed-switch-row"><span>Rodyti benziną</span><ha-switch id="ed-petrol"></ha-switch></div>
          <div class="ed-switch-row"><span>Rodyti dyzeliną</span><ha-switch id="ed-diesel"></ha-switch></div>
          <div class="ed-switch-row"><span>Rodyti dujas</span><ha-switch id="ed-lpg"></ha-switch></div>
        </div>
      </div>`;
      this._setupSelect("#ed-station", stationItems, c.station || "");
      this.querySelector("#ed-logo").checked = c.show_logo !== false;
      this.querySelector("#ed-petrol").checked = c.show_petrol !== false;
      this.querySelector("#ed-diesel").checked = c.show_diesel !== false;
      this.querySelector("#ed-lpg").checked = c.show_lpg !== false;
      this._updateFuelSwitches();
    }

    this._lastDataSig = this._dataSig();
    this._wire();
  }

  // ha-select: nauja versija naudoja .options + "selected" įvykį,
  // sena – mwc-list-item vaikus + "change". Palaikome abu.
  _setupSelect(sel, items, value) {
    const el = this.querySelector(sel);
    if (!el) return;
    if ("options" in el) {
      el.options = items;
      if (el.value !== value) el.value = value;
    } else {
      el.innerHTML = "";
      items.forEach(i => {
        const it = document.createElement("mwc-list-item");
        it.value = i.value;
        it.textContent = i.label;
        if (String(i.value) === String(value)) it.setAttribute("selected", "");
        el.appendChild(it);
      });
      if (el.value !== value) el.value = value;
    }
  }

  _emit(next) {
    if (this._lastEmitted && JSON.stringify(next) === JSON.stringify(this._lastEmitted)) return;
    this._lastEmitted = next;
    const ev = new Event("config-changed", { bubbles: true, composed: true });
    ev.detail = { config: next };
    this.dispatchEvent(ev);
  }

  _defaultStation() {
    const st = this._stations();
    if (st.length) return `${st[0].brand} - ${st[0].address}`;
    return "Neste - Marijampolė, Vilkaviškio g. 61D, 68153";
  }

  // Perjungikliai išjungiami, kai pasirinktoje degalinėje tokios kuro grupės kainos nėra
  // (pvz., Neste neturi dujų – „Rodyti dujas" tampa pilku ir neaktyviu).
  _updateFuelSwitches(stationKey) {
    const c = this._config || {};
    const key = stationKey !== undefined ? stationKey : (c.station || "");
    const stations = this._stations();
    const s = stations.find(x => `${x.brand} - ${x.address}` === key);
    const has = g => !!(s && (s.prices || []).some(p =>
      p.value && p.value !== "—" && p.value !== "unknown" && fuelGroup(p.label) === g));
    const set = (id, g) => {
      const el = this.querySelector(id);
      const row = el ? el.closest(".ed-switch-row") : null;
      const ok = has(g);
      if (el) el.disabled = !ok;
      if (row) row.classList.toggle("is-off", !ok);
    };
    set("#ed-petrol", "petrol");
    set("#ed-diesel", "diesel");
    set("#ed-lpg", "lpg");
  }

  _wire() {
    const q = id => this.querySelector(id);

    const selectValue = (ev, el) =>
      ev && ev.detail && ev.detail.value !== undefined ? ev.detail.value : el.value;

    const wireSelect = (id, key, after) => {
      const el = q(id);
      if (!el) return;
      const handler = ev => {
        const val = selectValue(ev, el);
        if (!val) return;
        if (el.value !== val) el.value = val;
        this._emit({ ...(this._config || {}), [key]: val });
        if (after) after();
      };
      el.addEventListener("selected", handler);
      el.addEventListener("change", handler);
    };

    wireSelect("#ed-fuel", "fuel");
    wireSelect("#ed-station", "station", () => {
      const val = q("#ed-station")?.value;
      this._updateFuelSwitches(val);
    });

    const wireSwitch = (id, key) => {
      const el = q(id);
      if (!el) return;
      el.addEventListener("change", () => {
        this._emit({ ...(this._config || {}), [key]: !!el.checked });
      });
    };

    wireSwitch("#ed-logo", "show_logo");
    wireSwitch("#ed-petrol", "show_petrol");
    wireSwitch("#ed-diesel", "show_diesel");
    wireSwitch("#ed-lpg", "show_lpg");
  }
}

// Apsauga nuo dvigubos registracijos (pvz., jei korta įkelta ir rankiniu būdu).
if (!customElements.get("fuel-prices-card-editor")) {
  customElements.define("fuel-prices-card-editor", FuelPricesCardEditor);
}
if (!customElements.get("fuel-prices-card")) {
  customElements.define("fuel-prices-card", FuelPricesCard);
}

// Registracija į HA kortelių parinkiklį
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "fuel-prices-card")) {
  window.customCards.push({
    type: "fuel-prices-card",
    name: "Degalų kainos Lietuvoje",
    description: "Degalų kainų Lietuvoje suvestinė ir degalinės kortelė",
    preview: true
  });
}
