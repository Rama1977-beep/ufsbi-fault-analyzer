import os
import sys
import pandas as pd

# ==============================================================================
# 1. REAL-WORLD INTERLOCKING RELAY CONTACT GRID (S&T Wiring Sheet Standard)
# ==============================================================================
RELAY_DB = {
    "SMKPR": {
        "function": "Station Master Key Proving Relay (Pre-Initiation Check)",
        "expected_after": "Power ON",
        "probable_cause": "SM Key is physically OUT, or Panel Key Contact has heavy carbon / open circuit",
        "feed_path": [
            {"relay": "SM_PANEL_KEY", "contact": "Band-1 & Band-2", "type": "Physical Key Switch Contacts"},
            {"unit": "Go to Plexiglass Panel Terminal Row-A: Check Fuse No. F1 (Pnl)"}
        ]
    },
    "SNR": {
        "function": "Signal Normal Proving Relay (Pre-Initiation Safety)",
        "expected_after": "SMKPR",
        "probable_cause": "Yard Signal Knob reversed, or Home/LSS Signal Aspect Lamp Fused / Bobbing",
        "feed_path": [
            {"relay": "ASCR / HSCR", "contact": "A1 & A2", "type": "Back Contacts (Signal ON Proving)"},
            {"unit": "Go to Relay Rack No. 3, Cable Termination Board (CTB): Test Terminal 12"}
        ]
    },
    "ASR": {
        "function": "Approach Locking Proving Relay (Pre-Initiation Safety)",
        "expected_after": "SNR",
        "probable_cause": "LSS Track Circuit / Advanced Starter Approach Track down or chattering",
        "feed_path": [
            {"relay": "FSTR (First Stop Track)", "contact": "A1 & A2", "type": "Front Contacts"},
            {"unit": "Go to Track Relay Cabinet: Test Terminal Row-C for incoming track voltage"}
        ]
    },
    "BIPR1": {
        "function": "UFSBI Vital System Health Relay 1",
        "expected_after": "ASR",
        "probable_cause": "Power input failure at UFSBI Dashboard or Internal DC-DC Converter output < 21.6V",
        "feed_path": [
            {"unit": "Go to Deltron Cabinet Sub-Rack 1: Check Power Supply Module Card-1 Output"},
            {"unit": "Go to Cabinet Terminal Block TB-1: Measure Voltage at Pins 5 & 6"}
        ]
    },
    "BIPR2": {
        "function": "UFSBI Vital System Health Relay 2",
        "expected_after": "BIPR1",
        "probable_cause": "System Hardware Code Trip (Phase Latch Lock) or Power input drop below 19V",
        "feed_path": [
            {"unit": "Go to Deltron Cabinet Sub-Rack 1: Check Power Supply Module Card-2 Output"},
            {"unit": "Go to Cabinet Terminal Block TB-1: Measure Voltage at Pins 7 & 8"}
        ]
    },
    "TGTNR": {
        "function": "Train Going To Normal Relay",
        "expected_after": "BIPR2",
        "probable_cause": "Block Instrument not in Line Closed state or LCZR back contact open",
        "feed_path": [
            {"relay": "LCZR", "contact": "C3 & C4", "type": "Back Contacts"},
            {"unit": "Go to Block Rack Layout: Test Binding Post Terminal 4B"}
        ]
    },
    "BPNR": {
        "function": "Block Button Proving Normal Relay",
        "expected_after": "TGTNR",
        "probable_cause": "Bell Plunger or TGB/TCB Button stuck in pressed position / Defective Contact",
        "feed_path": [
            {"relay": "BELL_PLUNGER_SWITCH", "contact": "Back-Band", "type": "Push Button Contacts"},
            {"unit": "Go to SM Panel Jumper Grid: Test Row-B, Pin 3 for stuck contact"}
        ]
    },
    "TGTR": {
        "function": "Train Going To Control Relay",
        "expected_after": "BPNR",
        "probable_cause": "Line Clear Initiation Failure or Bell Button Contact Defective",
        "feed_path": [
            {"relay": "TGTXR", "contact": "A4 & A5", "type": "Front Contacts"},
            {"relay": "BPNR", "contact": "C1 & C2", "type": "Front Contacts"},
            {"unit": "Go to TGTR Relay Base: Check Coil Terminal Wire Interconnections for loose solder"}
        ]
    },
    "TGTXR": {
        "function": "Train Going To Extension Relay",
        "expected_after": "TGTR",
        "probable_cause": "Circuit Handshake interruption or Link Fail between Dashboard & Cabinet",
        "feed_path": [
            {"relay": "TGTR", "contact": "A1 & A2", "type": "Front Contacts"},
            {"unit": "Go to Deltron Rack: Check UFSBI Digital Output Card connection to TGTXR Coil Input"}
        ]
    },
    "TCFR": {
        "function": "Train Coming From Control Relay",
        "expected_after": "TGTXR",
        "probable_cause": "Communication Receive (Rx) Path Failure / Quad Cable Core Cut / High Attenuation",
        "feed_path": [
            {"relay": "BIPR1", "contact": "A4 & A5", "type": "Front Contacts"},
            {"relay": "BIPR2", "contact": "D1 & D2", "type": "Front Contacts"},
            {"relay": "TGTR", "contact": "B3 & B4", "type": "Front Contacts"},
            {"unit": "Go to UFSBI Output Card: Test Terminal Row-E for active Rx output voltage"}
        ]
    },
    "BTSR": {
        "function": "Block Tension Signal Relay",
        "expected_after": "TCFR",
        "probable_cause": "Line clear acknowledgement fail from adjacent station",
        "feed_path": [
            {"relay": "TCFR", "contact": "B1 & B2", "type": "Front Contacts"},
            {"unit": "Go to Interlocking Rack Fuse Board: Check Fuse F5"}
        ]
    },
    "HSATPR": {
        "function": "Home Signal Approach Track Proving Relay",
        "expected_after": "BTSR",
        "probable_cause": "Train entry sequence failure or track circuit parameters unfulfilled",
        "feed_path": [
            {"relay": "BER_TR (Track Relay)", "contact": "C3 & C4", "type": "Front Contacts"},
            {"unit": "Go to Relay Room Terminal Block: Test TB-Home for drop in feed"}
        ]
    },
    "TAR1": {
        "function": "Time Arrival Relay 1 (Track Sequence Proving)",
        "expected_after": "HSATPR",
        "probable_cause": "Home Signal Replacement Sequence Fault or Axle Counter Reset Issue",
        "feed_path": [
            {"relay": "BTSR", "contact": "D1 & D2", "type": "Front Contacts"},
            {"relay": "HSATPR", "contact": "A1 & A2", "type": "Back Contacts"},
            {"unit": "Go to TAR1 Relay Base: Check Coil Terminal Base Binding Post for voltage"}
        ]
    },
    "TAR2": {
        "function": "Time Arrival Relay 2 (Complete Arrival Verification)",
        "expected_after": "TAR1",
        "probable_cause": "Arrival Sequence Timed-out or Interlocking Verification Parameters Unfulfilled",
        "feed_path": [
            {"relay": "TAR1", "contact": "A1 & A2", "type": "Front Contacts"},
            {"relay": "AZTR-R", "contact": "B3 & B4", "type": "Front Contacts"},
            {"relay": "FR1", "contact": "C1 & C2", "type": "Flashing Contacts"},
            {"unit": "Go to TAR2 Relay Base: Check Coil Terminal Connectors for proper seating"}
        ]
    }
}

STANDARD_SEQUENCE = ["SMKPR", "SNR", "ASR", "BIPR1", "BIPR2", "TGTNR", "BPNR", "TGTR", "TGTXR", "TCFR", "BTSR", "HSATPR", "TAR1", "TAR2"]

class RealWorldUFSBIAnalyzer:
    def sanitize_relay_name(self, cell_value):
        if pd.isna(cell_value):
            return ""
        cell_str = str(cell_value).upper()
        for relay in STANDARD_SEQUENCE:
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
            return {"status": "NO_DATA", "message": "Zero active UFSBI transitions found in log."}

        picked_relays = set()
        last_healthy_relay = None
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
# 5. UNIVERSAL RUNTIME INTERFACE (FOR PC CMD AND ANDROID WEB LINK)
# ==============================================================================
if __name__ == "__main__":
    analyzer = RealWorldUFSBIAnalyzer()
    
    # Check if running in Streamlit Mobile/Web environment
    try:
        import streamlit as st
        
        st.markdown("## 📡 UFSBI Master Diagnostic & Fault Isolation Engine")
        st.markdown("### **S&T Department - Northeast Frontier Railway**")
        st.markdown("---")
        
        uploaded_file = st.file_uploader("📥 Upload Station Data Logger Excel File (.xls/.xlsx)", type=["xls", "xlsx"])
        
        if uploaded_file is not None:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            log_events = analyzer.load_railway_logger(tmp_path)
            results = analyzer.analyze_sequence(log_events)
            
            st.markdown(f"### 📋 ROOT CAUSE ANALYSIS FOR: `{uploaded_file.name}`")
            st.markdown("---")
            
            if results["status"] == "HEALTHY":
                st.success(f"🟢 **DIAGNOSTIC STATUS: SYSTEM HEALTHY**\n\n{results['message']}")
            elif results["status"] == "NO_DATA":
                st.warning(f"⚠️ {results['message']}")
            else:
                missing = results["missing_relay"]
                last_healthy = results["last_healthy"]
                details = results["root_cause_details"]
                
                st.error(f"🚨 **BREAK POINT IDENTIFIED : [ {missing} ] Relay Failed to Pick Up**")
                st.info(f"⏱️ **LAST VALID SEQUENT STATE: [ {last_healthy if last_healthy else 'None (Power ON Phase)'} ]**")
                
                if details:
                    st.markdown(f"**Circuit Block Function :** {details['function']}")
                    st.markdown(f"**Isolating Root Cause   :** {details['probable_cause']}")
                    st.markdown("---")
                    st.markdown("### 🛠️ **WIRING FEED PATH PHYSICAL CHECKPOINTS**")
                    st.markdown("*(Isolate circuitry failures by measuring contact voltage drops sequentially at specified terminals)*")
                    
                    for idx, path in enumerate(details["feed_path"], 1):
                        if "relay" in path:
                            st.info(f"📍 **[{idx}] Check AT RELAY:** [ **{path['relay']}** ]\n* **Measure at Terminal Pins:** `{path['contact']}`\n* **Contact Type:** {path['type']}")
                        else:
                            st.error(f"⚡ **[{idx}] Check Physical Unit:** {path['unit']}")
                else:
                    st.write("Description: Relay sequence dropped unexpectedly.")
            os.unlink(tmp_path)

    except ImportError:
        # Fallback to local PC Command Prompt Execution Mode
        workspace_folder = "."
        all_files = os.listdir(workspace_folder)
        excel_files = [f for f in all_files if f.endswith(('.xls', '.xlsx'))]
        
        if excel_files:
            selected_file = excel_files[0]
            log_events = analyzer.load_railway_logger(os.path.join(workspace_folder, selected_file))
            results = analyzer.analyze_sequence(log_events)
            
            print(f"\n===========================================================================")
            print(f"BREAK POINT IDENTIFIED : [ {results.get('missing_relay')} ] Relay Failed to Pick Up")
            details = results.get('root_cause_details')
            if details:
                print(f"Isolating Root Cause   : {details['probable_cause']}\n")
                print("------------- WIRING FEED PATH PHYSICAL CHECKPOINTS -------------")
                for idx, path in enumerate(details["feed_path"], 1):
                    if "relay" in path:
                        print(f" [{idx}] Check AT RELAY: [ {path['relay']} ] -> Pins: {path['contact']} ({path['type']})")
                    else:
                        print(f" [{idx}] Check Unit    : {path['unit']}")
            print(f"===========================================================================\n")
