package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"regexp"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

const (
	PICO_PASSWORD = "12345678" // Default Pico AP password
	PICO_IP       = "192.168.4.1"
	PICO_PORT     = "80"
)

// Styles
var (
	titleStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("205")).
			MarginBottom(1)

	selectedStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("170")).
			Bold(true).
			PaddingLeft(2)

	normalStyle = lipgloss.NewStyle().
			PaddingLeft(4)

	errorStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("196")).
			Bold(true)

	successStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("42")).
			Bold(true)

	inputStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("86"))

	promptStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("205")).
			Bold(true)
)

type step int

const (
	stepListingPicos step = iota
	stepSelectingPico
	stepConnectingToPico
	stepEnteringSSID
	stepEnteringPassword
	stepEnteringUserID
	stepSendingCredentials
	stepComplete
	stepError
)

type network struct {
	SSID     string
	Signal   string
	IsPico   bool
	IsActive bool
}

type model struct {
	step         step
	networks     []network
	picoNetworks []network
	cursor       int
	selectedPico *network
	homeSSID     string
	homePassword string
	userID       string
	currentInput string
	message      string
	err          error
	quitting     bool
}

type networksFoundMsg []network
type connectionSuccessMsg struct{}
type sendSuccessMsg struct{}
type errMsg struct{ err error }

func (e errMsg) Error() string { return e.err.Error() }

func initialModel() model {
	return model{
		step:         stepListingPicos,
		networks:     []network{},
		picoNetworks: []network{},
		cursor:       0,
	}
}

func (m model) Init() tea.Cmd {
	return listNetworks
}

func listNetworks() tea.Msg {
	cmd := exec.Command("netsh", "wlan", "show", "networks", "mode=bssid")
	output, err := cmd.Output()
	if err != nil {
		return errMsg{fmt.Errorf("failed to list networks: %w", err)}
	}

	networks := parseNetworks(string(output))
	return networksFoundMsg(networks)
}

func parseNetworks(output string) []network {
	var networks []network
	lines := strings.Split(output, "\n")

	var currentSSID string
	var currentSignal string
	picoPattern := regexp.MustCompile(`(?i)^Pico-[0-9a-fA-F]+$`)

	for _, line := range lines {
		line = strings.TrimSpace(line)

		if strings.HasPrefix(line, "SSID") && !strings.Contains(line, "BSSID") {
			parts := strings.SplitN(line, ":", 2)
			if len(parts) == 2 {
				ssid := strings.TrimSpace(parts[1])
				if ssid != "" {
					currentSSID = ssid
				}
			}
		}

		if strings.HasPrefix(line, "Signal") {
			parts := strings.SplitN(line, ":", 2)
			if len(parts) == 2 {
				currentSignal = strings.TrimSpace(parts[1])
			}
		}

		// When we have both SSID and Signal, add the network
		if currentSSID != "" && currentSignal != "" {
			isPico := picoPattern.MatchString(currentSSID)
			networks = append(networks, network{
				SSID:   currentSSID,
				Signal: currentSignal,
				IsPico: isPico,
			})
			currentSSID = ""
			currentSignal = ""
		}
	}

	return networks
}

func connectToNetwork(ssid, password string) tea.Cmd {
	return func() tea.Msg {
		// Check if profile exists, if not create it
		profileXML := fmt.Sprintf(`<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
	<name>%s</name>
	<SSIDConfig>
		<SSID>
			<name>%s</name>
		</SSID>
	</SSIDConfig>
	<connectionType>ESS</connectionType>
	<connectionMode>auto</connectionMode>
	<MSM>
		<security>
			<authEncryption>
				<authentication>WPA2PSK</authentication>
				<encryption>AES</encryption>
				<useOneX>false</useOneX>
			</authEncryption>
			<sharedKey>
				<keyType>passPhrase</keyType>
				<protected>false</protected>
				<keyMaterial>%s</keyMaterial>
			</sharedKey>
		</security>
	</MSM>
</WLANProfile>`, ssid, ssid, password)

		// Create temporary profile file
		tmpFile, err := os.CreateTemp("", "wifi-profile-*.xml")
		if err != nil {
			return errMsg{fmt.Errorf("failed to create temp file: %w", err)}
		}
		defer os.Remove(tmpFile.Name())

		if _, err := tmpFile.WriteString(profileXML); err != nil {
			return errMsg{fmt.Errorf("failed to write profile: %w", err)}
		}
		tmpFile.Close()

		// Add profile
		cmd := exec.Command("netsh", "wlan", "add", "profile", fmt.Sprintf("filename=%s", tmpFile.Name()), "user=all")
		if err := cmd.Run(); err != nil {
			// Profile might already exist, continue anyway
		}

		// Connect to network
		cmd = exec.Command("netsh", "wlan", "connect", fmt.Sprintf("name=%s", ssid))
		if err := cmd.Run(); err != nil {
			return errMsg{fmt.Errorf("failed to connect: %w", err)}
		}

		// Wait for connection (may take up to 15 seconds)
		for i := 0; i < 15; i++ {
			time.Sleep(1 * time.Second)

			// Verify connection
			cmd = exec.Command("netsh", "wlan", "show", "interfaces")
			output, err := cmd.Output()
			if err == nil && strings.Contains(string(output), ssid) && strings.Contains(string(output), "connected") {
				return connectionSuccessMsg{}
			}
		}

		return errMsg{fmt.Errorf("connection timeout after 15 seconds")}
	}
}

func sendCredentials(ssid, password, userID string) tea.Cmd {
	return func() tea.Msg {
		// Check if Pico is ready
		checkURL := fmt.Sprintf("http://%s:%s/", PICO_IP, PICO_PORT)
		client := &http.Client{Timeout: 15 * time.Second}

		resp, err := client.Get(checkURL)
		if err != nil {
			return errMsg{fmt.Errorf("Pico not reachable at %s: %w", PICO_IP, err)}
		}
		resp.Body.Close()

		// Send credentials
		payload := map[string]string{
			"ssid":     ssid,
			"password": password,
			"user_id":  userID,
		}

		jsonData, err := json.Marshal(payload)
		if err != nil {
			return errMsg{fmt.Errorf("failed to encode credentials: %w", err)}
		}

		credURL := fmt.Sprintf("http://%s:%s/credentials", PICO_IP, PICO_PORT)
		req, err := http.NewRequest("POST", credURL, bytes.NewBuffer(jsonData))
		if err != nil {
			return errMsg{fmt.Errorf("failed to create request: %w", err)}
		}
		req.Header.Set("Content-Type", "application/json")

		resp, err = client.Do(req)
		if err != nil {
			return errMsg{fmt.Errorf("failed to send credentials: %w", err)}
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			return errMsg{fmt.Errorf("Pico returned status %d: %s", resp.StatusCode, string(body))}
		}

		return sendSuccessMsg{}
	}
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c", "q":
			m.quitting = true
			return m, tea.Quit

		case "up", "k":
			if m.step == stepSelectingPico && m.cursor > 0 {
				m.cursor--
			}

		case "down", "j":
			if m.step == stepSelectingPico && m.cursor < len(m.picoNetworks)-1 {
				m.cursor++
			}

		case "enter":
			switch m.step {
			case stepSelectingPico:
				if len(m.picoNetworks) > 0 {
					m.selectedPico = &m.picoNetworks[m.cursor]
					m.step = stepConnectingToPico
					m.message = fmt.Sprintf("Connecting to %s...\n(This may take up to 15 seconds)", m.selectedPico.SSID)
					return m, connectToNetwork(m.selectedPico.SSID, PICO_PASSWORD)
				}

			case stepEnteringSSID:
				if m.currentInput != "" {
					m.homeSSID = m.currentInput
					m.currentInput = ""
					m.step = stepEnteringPassword
				}

			case stepEnteringPassword:
				if m.currentInput != "" {
					m.homePassword = m.currentInput
					m.currentInput = ""
					m.step = stepEnteringUserID
				}

			case stepEnteringUserID:
				// User ID is optional
				m.userID = m.currentInput
				if m.userID == "" {
					m.userID = "default_user"
				}
				m.step = stepSendingCredentials
				m.message = "Sending credentials to Pico..."
				return m, sendCredentials(m.homeSSID, m.homePassword, m.userID)

			case stepComplete, stepError:
				m.quitting = true
				return m, tea.Quit
			}

		case "backspace":
			if len(m.currentInput) > 0 {
				m.currentInput = m.currentInput[:len(m.currentInput)-1]
			}

		default:
			// Handle text input for SSID, password, and userID
			if m.step == stepEnteringSSID || m.step == stepEnteringPassword || m.step == stepEnteringUserID {
				m.currentInput += msg.String()
			}
		}

	case networksFoundMsg:
		m.networks = []network(msg)
		// Filter only Pico networks
		m.picoNetworks = []network{}
		for _, net := range m.networks {
			if net.IsPico {
				m.picoNetworks = append(m.picoNetworks, net)
			}
		}

		if len(m.picoNetworks) == 0 {
			m.step = stepError
			m.err = fmt.Errorf("no Pico networks found")
		} else {
			m.step = stepSelectingPico
		}

	case connectionSuccessMsg:
		m.step = stepEnteringSSID
		m.message = successStyle.Render("✓ Connected to Pico!")

	case sendSuccessMsg:
		m.step = stepComplete
		m.message = successStyle.Render("✓ Credentials sent successfully!\n\nPico will now:\n  1. Disconnect from AP\n  2. Connect to your home WiFi\n  3. Register with the server\n\nPress Enter to exit.")

	case errMsg:
		m.step = stepError
		m.err = msg.err

	}

	return m, nil
}

func (m model) View() string {
	if m.quitting {
		return ""
	}

	var s strings.Builder

	// Title
	s.WriteString(titleStyle.Render("🔧 Pico WiFi Setup Tool"))
	s.WriteString("\n\n")

	switch m.step {
	case stepListingPicos:
		s.WriteString("Scanning for Pico devices...\n")

	case stepSelectingPico:
		s.WriteString(promptStyle.Render("Select a Pico device:"))
		s.WriteString("\n\n")

		for i, net := range m.picoNetworks {
			cursor := " "
			style := normalStyle
			if m.cursor == i {
				cursor = ">"
				style = selectedStyle
			}
			s.WriteString(fmt.Sprintf("%s %s (%s)\n", cursor, style.Render(net.SSID), net.Signal))
		}

		s.WriteString("\n")
		s.WriteString("Use ↑/↓ to select, Enter to connect, q to quit\n")

	case stepConnectingToPico:
		s.WriteString(m.message)
		s.WriteString("\n")

	case stepEnteringSSID:
		if m.message != "" {
			s.WriteString(m.message)
			s.WriteString("\n\n")
		}
		s.WriteString(promptStyle.Render("Enter your home WiFi SSID:"))
		s.WriteString("\n")
		s.WriteString(inputStyle.Render("> " + m.currentInput))
		s.WriteString("\n\n")
		s.WriteString("Press Enter when done\n")

	case stepEnteringPassword:
		s.WriteString(promptStyle.Render(fmt.Sprintf("Enter password for '%s':", m.homeSSID)))
		s.WriteString("\n")
		// Show dots instead of actual password
		dots := strings.Repeat("•", len(m.currentInput))
		s.WriteString(inputStyle.Render("> " + dots))
		s.WriteString("\n\n")
		s.WriteString("Press Enter when done\n")

	case stepEnteringUserID:
		s.WriteString(promptStyle.Render("Enter User ID (optional, press Enter to use 'default_user'):"))
		s.WriteString("\n")
		s.WriteString(inputStyle.Render("> " + m.currentInput))
		s.WriteString("\n\n")
		s.WriteString("Press Enter when done\n")

	case stepSendingCredentials:
		s.WriteString(m.message)
		s.WriteString("\n")

	case stepComplete:
		s.WriteString(m.message)
		s.WriteString("\n")

	case stepError:
		s.WriteString(errorStyle.Render("✗ Error: "))
		s.WriteString(m.err.Error())
		s.WriteString("\n\n")
		s.WriteString("Press Enter or q to quit\n")
	}

	return s.String()
}

func main() {
	p := tea.NewProgram(initialModel())
	if _, err := p.Run(); err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}
}
