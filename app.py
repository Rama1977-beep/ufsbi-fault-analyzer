import os
import pandas as pd
import streamlit as st

# ==============================================================================
# 1. MASTER INTERLOCKING RELAY CONTACT GRID (Deltron UFSBI RE Area Standard)
# ==============================================================================
RELAY_DB = {
    "TCFR": {
        "function": "Train Coming From Control Relay",
        "expected_after": "TGTR",
        "probable_cause": "Communication Receive (Rx) Path Failure or Line Interruption",
        "feed_path": [
            {"relay": "BIPR1", "contact": "A4-A5", "type": "Front"},
            {"relay": "BIPR2", "contact": "D1-D2", "type": "Front"},
            {"relay": "TGTR", "contact": "B3-B4", "type": "Front"},
            {"unit": "UFSBI Digital Output Card to TCFR Coil Terminal Input"}
        ]
    },
    "TGTR": {
        "function": "Train Going To Control Relay",
        "expected_after": "TGTNR",
        "probable_cause": "Line Clear Initiation Failure or Bell Plunger Contact Open Circuit",
        "feed_path": [
            {"relay": "TGTXR", "contact": "A4-A5", "type": "Front"},
            {"relay": "BPNR", "contact": "C1-C2", "type": "Front"},
            {"unit": "TGTR Coil Terminal Wire Interconnection"}
        ]
    },
    "TAR1": {
        "function": "Time Arrival Relay 1 (Track Sequence Proving)",
        "expected_after": "HSATPR",
        "probable_cause": "Home Signal Replacement Track Sequence Fault or Axle Counter Reset Issue",
        "feed_path": [
            {"relay": "BTSR", "contact": "D1-D2", "type": "Front"},
            {"relay": "HSATPR", "contact": "A1-A2", "type": "Back"},
            {"unit": "TAR1 Coil Terminal Base Binding Post"}
        ]
    },
    "TAR2": {
        "function": "Time Arrival Relay 2 (Complete Arrival Proving Verification)",
        "expected_after": "TAR1",
        "probable_cause": "Arrival Sequence Timed-out or Interlocking Verification Parameters Unfulfilled",
        "feed_path": [
            {"relay": "TAR1", "contact": "A1-A2", "type": "Front"},
            {"relay": "AZTR-R", "contact": "B3-B4", "type": "Front"},
            {"relay": "FR1", "contact": "C1-C2", "type": "Flashing"},
            {"unit": "TAR2 Coil Terminal Connector"}
        ]
    }
}

STANDARD_SEQUENCE = ["TGTNR", "BPNR", "TGTR", "TGTXR", "TCFR", "BTSR", "HSATPR", "TAR1", "TAR2"]

class WebUFSBIAnalyzer:
    def sanitize_relay_name(self, cell_value):
        if pd.isna(cell_value):
            return ""
        cell_str = str(cell_value).upper()
        for relay in STANDARD_SEQUENCE:
            if relay in cell_str:
                return relay
        return ""

    def process_logger_data(self, uploaded_file):
        try:
            df = pd.read_excel(uploaded_file)
            df.columns = [str(col).strip().upper() for col in df.columns]
            
            time_col = next((c for c in df.columns if "TIME" in c or "DATE" in c), None)
            relay_col = next((c for c in df.columns if "RELAY" in c or "DESC" in c or "NAME" in c), None)
            status_col = next((c for c in df.columns if "STAT" in c or "STATE" in c or "VAL" in c), None)
            
            if not time_col: time_col = df.columns[0]
            if not relay_col: relay_col = df.columns[1]
            if not status_col: status_col = df.columns[2]
            
            events = []
            for _, row in df.iterrows():
                relay_name = self.sanitize_relay_name(row[relay_col])
                if relay_name:
                    events.append({
                        "time": str(row[time_col]),
                        "relay": relay_name,
                        "status": str(row[status_col]).upper()
                    })
            return events
        except Exception as e:
            st.error(f"Failed to parse the file: {str(e)}")
            return None

    def analyze_sequence(self, events):
        if not events:
            return {"status": "NO_DATA", "message": "Zero active UFSBI transitions found in log."}

        picked_relays = set()
        last_healthy_relay = "None"
        missing_relay = None

        for relay in STANDARD_SEQUENCE:
            is_picked = any(
                e['relay'] == relay and 
                any(x in e['status'] for x in ['ON', 'PICK', 'UP', '1', 'REVERS']) 
                for e in events
            )
            if is_picked:
                picked_relays.add(relay)
                last_healthy_relay = relay
            else:
                missing_relay = relay
                break

        if not missing_relay:
            return {"status": "HEALTHY", "message": "All signaling relays picked up in proper operational sequence."}

        return {
            "status": "FAILURE",
            "missing_relay": missing_relay,
            "last_healthy": last_healthy_relay,
            "root_cause_details": RELAY_DB.get(missing_relay, None)
        }

# ==============================================================================
# STREAMLIT WEB INTERFACE CONFIGURATION
# ==============================================================================
st.set_page_config(page_title="UFSBI Fault Analyzer", page_icon="🎛️", layout="centered")

st.title("🎛️ UFSBI Web Fault Isolator")
st.write("Upload raw data logger telemetry spreadsheets directly from your smartphone to diagnose interlocking circuit drops.")

analyzer = WebUFSBIAnalyzer()

# Native Browser File Upload Button
uploaded_file = st.file_uploader("Choose Data Logger Excel File (.xls, .xlsx)", type=["xls", "xlsx"])

if uploaded_file is not None:
    st.info(f"Processing File: {uploaded_file.name}")
    events = analyzer.process_logger_data(uploaded_file)
    
    if events:
        result = analyzer.analyze_sequence(events)
        
        st.subheader("Diagnostic Results")
        
        if result["status"] == "HEALTHY":
            st.success(result["message"])
            
        elif result["status"] == "NO_DATA":
            st.warning(result["message"])
            
        elif result["status"] == "FAILURE":
            missing = result["missing_relay"]
            last_healthy = result["last_healthy"]
            details = result["root_cause_details"]
            
            # Highlight Breakpoint in Red
            st.error(f"BREAKPOINT IDENTIFIED: [ {missing} ] Relay Failed to Pick Up")
            st.markdown(f"**Last Stable Register:** `{last_healthy}` Relay successfully documented UP.")
            
            if details:
                st.markdown(f"### Subsystem Block Function:\n{details['function']}")
                st.markdown(f"### Isolating Root Cause:\n**{details['probable_cause']}**")
                
                st.write("---")
                st.subheader("⚡ Wiring Feed Path Physical Checkpoints")
                st.write("Measure physical contact loop voltage drops sequentially to track faults:")
                
                for idx, path in enumerate(details["feed_path"], 1):
                    if "relay" in path:
                        st.markdown(f"**[{idx}] Check Relay:** `{path['relay']}`")
                        st.write(f"👉 Pin Node Contact Terminal: {path['contact']} ({path['type']} Contact Configuration)")
                    else:
                        st.markdown(f"**[{idx}] Check Unit Box Interface:**")
                        st.write(f"👉 {path['unit']}")
            else:
                st.write("Interlocking relay dropped out unexpectedly. Verify core terminal wiring matrices.")
