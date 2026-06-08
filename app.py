
import os
import sys
import pandas as pd

# ==============================================================================
# 1. REAL-WORLD DOUBLE LINE & SINGLE LINE UFSBI RELAY MATRIX (S&T Wiring Standard)
# ==============================================================================
RELAY_DB = {
    "LINK_FAIL": {
        "function": "UFSBI Inter-Station Line Communication Link",
        "probable_cause": "🚨 CRITICAL LINK FAILURE! OFC Cable Core Cut, High Line Attenuation (>30dB), or Deltron Rx/Tx Card failure.",
        "feed_path": [
            {"unit": "Go to Deltron Cabinet CPU Card: Check if 'LINK FAIL' LED or Error Code 33 is flashing."},
            {"unit": "Go to OFC MUX / Quad Cable Termination Box: Measure optical power dB loss with Optical Power Meter."},
            {"unit": "Verify adjacent station's UFSBI is not completely powered OFF / Fuse Blown."}
        ]
    },
    "POWER_FAIL": {
        "function": "UFSBI Internal Vital Power Proving (BIPR1/BIPR2 Drop)",
        "probable_cause": "⚡ CABINET POWER SUPPLY FAULT! Main 24V DC input dropped below operational limits (<21.6V) or DC-DC Converter blown.",
        "feed_path": [
            {"unit": "Go to Deltron Cabinet TB-1: Measure Voltage across Pins 5 & 6 (BIPR1) and Pins 7 & 8 (BIPR2)."},
            {"unit": "Check Sub-Rack Power Supply Module Card-1 & Card-2 status LEDs."},
            {"unit": "Check 2A/4A Glass Fuse on the power distribution panel."}
        ]
    },
    "LCZR": {
        "function": "Line Closed Proving Relay (Double Line Normal State Lock)",
        "probable_cause": "🔒 BLOCK SECTION NOT CLOSED! Block Instrument is still in TOL (Train on Line) or Line Clear condition, or BPAC Axle Counter failed to reset.",
        "feed_path": [
            {"relay": "AZTR (BPAC Axle Counter Proving Relay)", "contact": "A1 & A2", "type": "Front Contacts"},
            {"relay": "SM_PANEL_KEY_SWITCH", "contact": "Band-1 & Band-2", "type": "Physical Key Contacts"},
            {"unit": "Go to Axle Counter Reset Box: Check if Preparatory Reset is required to normalize section."}
        ]
    },
    "LSSPR": {
        "function": "Last Stop Signal Proving Relay (Advanced Starter Interlocking)",
        "probable_cause": "🚫 LSS SIGNAL CLEARANCE FAULT! Last Stop Signal knob is not reversed, or Advanced Starter track circuit is DOWN/Chattering.",
        "feed_path": [
            {"relay": "LSS_GN_CR (Signal Knob Proving)", "contact": "A3 & A4", "type": "Front Contacts"},
            {"relay": "LSS_FVT_R (First Vehicle Track Relay)", "contact": "C1 & C2", "type": "Front Contacts"},
            {"unit": "Go to Relay Rack No. 2, CTB Board: Measure voltage at Terminal Pin 15 to verify LSS circuit continuity."}
        ]
    },
    "TOLR": {
        "function": "Train On Line Relay (Block Occupation Latch)",
        "probable_cause": "⚠️ TOL LATCHING FAULT! Train entered the section but TOLR failed to pick up locally, or sequential entry tracks failed to drop.",
        "feed_path": [
            {"relay": "LSS_FVT_R (First Vehicle Track)", "contact": "A1 & A2", "type": "Back Contacts (Vehicle Entry Proving)"},
            {"unit": "Go to Double Line Block Rack: Check TOL Latch Relay Coil Block for mechanical stuck or burnt coil."}
        ]
    },
    "BLR": {
        "function": "Block Lock Relay (Final Authorization Circuit)",
        "probable_cause": "❌ BLOCK LOCK RELEASE FAIL! Inter-station commutation handshake unfulfilled or lock magnet coil open circuit.",
        "feed_path": [
            {"relay": "BIPR1", "contact": "B1 & B2", "type": "Front Contacts"},
            {"relay": "BIPR2", "contact": "C3 & C4", "type": "Front Contacts"},
            {"unit": "Go to Instrument Base Binding Posts: Test Pins 3A & 3B for 24V DC Lock Pulse."}
        ]
    }
}

# Double Line & Single Line Cross-Check Points
CRITICAL_CHECKPOINTS = ["BIPR1", "BIPR2", "LCZR", "LSSPR", "TOLR", "BLR"]

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
            
            # Smart Chronological Sorting immediately before failure
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
            return {"status": "NO_DATA", "message": "Zero active UFSBI data points found in data logger sheet."}

        # Setup latest state configurations
        states = {r: "DOWN" for r in CRITICAL_CHECKPOINTS}
        for e in events:
            if any(x in e['status'] for x in ['ON', 'PICK', 'UP', '1', 'REVERS']):
                states[e['relay']] = "UP"
            elif any(x in e['status'] for x in ['OFF', 'DROP', 'DOWN', '0', 'NORMAL']):
                states[e['relay']] = "DOWN"

        # ----------------==================================================
        # PRIORITY GATE 1: CRITICAL LINK AND POWER SCAN (BIPR1 & BIPR2)
        # ----------------==================================================
        if states["BIPR1"] == "DOWN" and states["BIPR2"] == "DOWN":
            return {
                "status": "FAILURE",
                "missing_relay": "LINK FAILURE / LINE INTERRUPTION",
                "root_cause_details": RELAY_DB["LINK_FAIL"]
            }
        
        if states["BIPR1"] == "DOWN" or states["BIPR2"] == "DOWN":
            return {
                "status": "FAILURE",
                "missing_relay": "BIPR1 / BIPR2 (Power Input Drop)",
                "root_cause_details": RELAY_DB["POWER_FAIL"]
            }

        # ----------------==================================================
        # PRIORITY GATE 2: DOUBLE LINE OPERATION SCAN (LCZR / LSSPR / TOLR)
        # ----------------==================================================
        if states["LCZR"] == "DOWN":
            return {
                "status": "FAILURE",
                "missing_relay": "LCZR (Line Closed Lock Open)",
                "root_cause_details": RELAY_DB["LCZR"]
            }

        if states["LSSPR"] == "DOWN":
            return {
                "status": "FAILURE",
                "missing_relay": "LSSPR (Last Stop Signal Proving Circuit)",
                "root_cause_details": RELAY_DB["LSSPR"]
            }

        if states["TOLR"] == "DOWN":
            return {
                "status": "FAILURE",
                "missing_relay": "TOLR (Train On Line Circuit Fault)",
                "root_cause_details": RELAY_DB["TOLR"]
            }

        if states["BLR"] == "DOWN":
            return {
                "status": "FAILURE",
                "missing_relay": "BLR (Block Lock Release Fault)",
                "root_cause_details": RELAY_DB["BLR"]
            }

        return {"status": "HEALTHY", "message": "All monitored Double/Single Line UFSBI circuits working within safe parameters."}

# ==============================================================================
# 5. UNIVERSAL Streamlit Android UI & PC CLI Framework Gateway
# ==============================================================================
if __name__ == "__main__":
    analyzer = RealWorldUFSBIAnalyzer()
    try:
        import streamlit as st
        st.set_page_config(page_title="UFSBI Diagnostic Engine", layout="wide")
        st.markdown("## 📡 Advanced UFSBI Universal Diagnostic Engine")
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
        # Fallback local command prompt compatibility
        print("[INFO] Executing in local PC CLI Mode.")
