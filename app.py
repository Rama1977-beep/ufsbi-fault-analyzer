import os
import sys
import pandas as pd

# ==============================================================================
# 1. CORE UFSBI CABINET RELAY MAPPING (Pure Data Logger Input Parameters)
# ==============================================================================
RELAY_DB = {
    "LINK_FAIL": {
        "function": "UFSBI Inter-Station Line Communication Link",
        "probable_cause": "🚨 CRITICAL LINK FAILURE! OFC Cable Core Cut, High Line Attenuation (>30dB), or Deltron Rx/Tx Card failure.",
        "feed_path": [
            {"unit": "Go to Deltron Cabinet CPU Card: Check if 'LINK FAIL' LED or Error Code 33 is flashing."},
            {"unit": "Go to OFC MUX / Quad Cable Termination Box: Measure optical power dB loss."},
            {"unit": "Verify adjacent station's UFSBI is not completely powered OFF."}
        ]
    },
    "POWER_FAIL": {
        "function": "UFSBI Internal Vital Power Proving (BIPR1/BIPR2 Drop)",
        "probable_cause": "⚡ CABINET POWER SUPPLY FAULT! Main 24V DC input dropped below operational limits (<21.6V) or DC-DC Converter blown.",
        "feed_path": [
            {"unit": "Go to Deltron Cabinet TB-1 (Terminal Block): Measure Voltage across Pins 5 & 6 (BIPR1) and Pins 7 & 8 (BIPR2)."},
            {"unit": "Check Sub-Rack Power Supply Module Module Card-1 & Card-2 status LEDs."},
            {"unit": "Check 2A/4A Glass Fuse on the power distribution panel."}
        ]
    },
    "TGTNR": {
        "function": "Train Going To Normal Relay",
        "probable_cause": "🔑 BLOCK OPERATION BLOCKED / KEY ISSUE! Block Instrument is not in 'Line Closed' state, or local LCB Key/SM Key contact is open.",
        "feed_path": [
            {"relay": "LCZR (Line Closed Proving Relay)", "contact": "C3 & C4", "type": "Back Contacts"},
            {"relay": "SM_PANEL_KEY_SWITCH", "contact": "Band-1 & Band-2", "type": "Physical Key Contacts"},
            {"unit": "Go to SM Panel Board Jumper Grid Row-A: Verify Fuse No. F1 (Pnl) is intact."}
        ]
    },
    "BPNR": {
        "function": "Block Button Proving Normal Relay",
        "probable_cause": "🔘 BUTTON STUCK FAULT! Bell Plunger, TGB, or TCB button is physically stuck in pressed position or carboned.",
        "feed_path": [
            {"relay": "BELL_PLUNGER / PUSH_BUTTON", "contact": "Back-Band contacts", "type": "Normally Closed Switch"},
            {"unit": "Go to SM Panel Jumper Grid Row-B: Check Pin 3 for short circuit / terminal shorting."}
        ]
    },
    "TGTR": {
        "function": "Train Going To Control Relay (Line Clear Granted Lock)",
        "probable_cause": "❌ LINE CLEAR INITIATION FAIL! Circuit discontinuity in handshake parameters or open contact in local initiation loop.",
        "feed_path": [
            {"relay": "TGTXR", "contact": "A4 & A5", "type": "Front Contacts"},
            {"relay": "BPNR", "contact": "C1 & C2", "type": "Front Contacts"},
            {"unit": "Go to TGTR Relay Q-Style Base: Check Coil Terminals for loose wire or dry solder."}
        ]
    },
    "TCFR": {
        "function": "Train Coming From Control Relay (Line Clear Received)",
        "expected_after": "TGTR",
        "probable_cause": "📡 HANDSHAKE RESPONSE FAILURE! Local cabinet received the demand but failed to latch due to internal relay dependency drop.",
        "feed_path": [
            {"relay": "BIPR1", "contact": "A4 & A5", "type": "Front Contacts"},
            {"relay": "BIPR2", "contact": "D1 & D2", "type": "Front Contacts"},
            {"relay": "TGTR", "contact": "B3 & B4", "type": "Front Contacts"}
        ]
    }
}

# Criss-Cross Execution Sequence
CRITICAL_CHECKPOINTS = ["BIPR1", "BIPR2", "TGTNR", "BPNR", "TGTR", "TCFR"]

class RealWorldUFSBIAnalyzer:
    def sanitize_relay_name(self, cell_value):
        if pd.isna(cell_value):
            return ""
        cell_str = str(cell_value).upper()
        for relay in CRITICAL_CHECKPOINTS:
            if relay in cell_str:
                return relay
        return ""

    def load_railway_logger(self, file_path):
        try:
            df = pd.read_excel(file_path)
            df.columns = [str(col).strip().upper() for col in df.columns]
            
            time_col = next((c for c in df.columns if "TIME" in c or "DATE" in c), None)
            relay_col = next((c for c in df.columns if "RELAY" in c or "DESC" in c or "NAME" in c), None)
            status_col = next((c for c in df.columns if "STAT" in c or "STATE" in c or "VAL" in c), None)
            
            if not time_col: time_col = df.columns[0]
            if not relay_col: relay_col = df.columns[1]
            if not status_col: status_col = df.columns[2]
            
            # Sort chronologically by time to read state immediately BEFORE failure
            df = df.dropna(subset=[time_col, relay_col, status_col])
            df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
            df = df.sort_values(by=time_col).reset_index(drop=True)
            
            cleaned_events = []
            for _, row in df.iterrows():
                relay_name = self.sanitize_relay_name(row[relay_col])
                if relay_name:
                    cleaned_events.append({
                        "time": str(row[time_col]),
                        "relay": relay_name,
                        "status": str(row[status_col]).upper()
                    })
            return cleaned_events
        except Exception as e:
            return []

    def analyze_sequence(self, events):
        if not events:
            return {"status": "NO_DATA", "message": "Zero UFSBI data points found in data logger sheet."}

        # Extract latest states of vital relays
        states = {r: "DOWN" for r in CRITICAL_CHECKPOINTS}
        for e in events:
            if any(x in e['status'] for x in ['ON', 'PICK', 'UP', '1', 'REVERS']):
                states[e['relay']] = "UP"
            elif any(x in e['status'] for x in ['OFF', 'DROP', 'DOWN', '0', 'NORMAL']):
                states[e['relay']] = "DOWN"

        # ----------------==================================================
        # PRIORITY GATE 1: CHECK LINK AND SYSTEM POWER FIRST (BIPR1 & BIPR2)
        # ----------------==================================================
        if states["BIPR1"] == "DOWN" and states["BIPR2"] == "DOWN":
            return {
                "status": "FAILURE",
                "missing_relay": "LINK FAILURE / LINE INTERREUPTION",
                "type": "LINK",
                "root_cause_details": RELAY_DB["LINK_FAIL"]
            }
        
        if states["BIPR1"] == "DOWN" or states["BIPR2"] == "DOWN":
            return {
                "status": "FAILURE",
                "missing_relay": "BIPR1 / BIPR2 (Power Input Drop)",
                "type": "POWER",
                "root_cause_details": RELAY_DB["POWER_FAIL"]
            }

        # ----------------==================================================
        # PRIORITY GATE 2: CHECK KEYS AND BUTTONS ONLY IF LINK/POWER IS OK
        # ----------------==================================================
        if states["TGTNR"] == "DOWN":
            return {
                "status": "FAILURE",
                "missing_relay": "TGTNR",
                "type": "OPERATION",
                "root_cause_details": RELAY_DB["TGTNR"]
            }

        if states["BPNR"] == "DOWN":
            return {
                "status": "FAILURE",
                "missing_relay": "BPNR",
                "type": "OPERATION",
                "root_cause_details": RELAY_DB["BPNR"]
            }

        if states["TGTR"] == "DOWN":
            return {
                "status": "FAILURE",
                "missing_relay": "TGTR",
                "type": "OPERATION",
                "root_cause_details": RELAY_DB["TGTR"]
            }

        if states["TCFR"] == "DOWN":
            return {
                "status": "FAILURE",
                "missing_relay": "TCFR",
                "type": "OPERATION",
                "root_cause_details": RELAY_DB["TCFR"]
            }

        return {"status": "HEALTHY", "message": "All monitored UFSBI cabinet circuits working in perfect parameters."}

# ==============================================================================
# 5. UNIVERSAL Streamlit Android UI & PC CLI Framework
# ==============================================================================
if __name__ == "__main__":
    analyzer = RealWorldUFSBIAnalyzer()
    try:
        import streamlit as st
        st.set_page_config(page_title="UFSBI Diagnostic Engine", layout="wide")
        st.markdown("## 📡 Advanced UFSBI Diagnostic Engine (Priority-Scan Mode)")
        st.markdown("### **S&T Department — Northeast Frontier Railway**")
        st.markdown("---")
        
        uploaded_file = st.file_uploader("📥 Upload Station Data Logger Excel File", type=["xls", "xlsx"])
        if uploaded_file is not None:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            events = analyzer.load_railway_logger(tmp_path)
            res = analyzer.analyze_sequence(events)
            
            st.markdown(f"### 📋 RECTIFICATION REPORT FOR: `{uploaded_file.name}`")
            if res["status"] == "HEALTHY":
                st.success(res["message"])
            elif res["status"] == "NO_DATA":
                st.warning(res["message"])
            else:
                details = res["root_cause_details"]
                st.error(f"🚨 **CRITICAL BREAK POINT: {res['missing_relay']}**")
                st.info(f"ℹ️ **Isolating Cause:** {details['probable_cause']}")
                st.markdown("#### 🛠️ **FIELD INVESTIGATION PATH (STEP-BY-STEP):**")
                
                for idx, p in enumerate(details["feed_path"], 1):
                    if "relay" in p:
                        st.warning(f"📍 **[{idx}] Check AT RELAY:** [ **{p['relay']}** ] $\\rightarrow$ Pins: `{p['contact']}` ({p['type']})")
                    else:
                        st.error(f"⚡ **[{idx}] Action Point:** {p['unit']}")
            os.unlink(tmp_path)
    except ImportError:
        # Fallback for PC command prompt
        print("[INFO] Streamlit not detected. Executing in CLI Mode.")
