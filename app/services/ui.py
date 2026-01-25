import asyncio
from typing import Dict, List
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

class DashboardManager:
    """
    Manages a real-time dashboard in the terminal for multi-site scraping.
    """
    def __init__(self, sites: List[str]):
        self.console = Console()
        self.layout = Layout()
        self.sites = sites
        self.logs: Dict[str, List[str]] = {site: [] for site in sites}
        self.progress_data: Dict[str, float] = {site: 0.0 for site in sites}
        self.status_data: Dict[str, str] = {site: "Waiting..." for site in sites}
        
        # Build initial layout
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        # Split body into columns/rows based on number of sites
        # Assuming 5 sites, we can do 2 columns: 3 on left, 2 on right
        self.layout["body"].split_row(
            Layout(name="col1"),
            Layout(name="col2")
        )
        
        self.layout["col1"].split_column(
            Layout(name=sites[0]),
            Layout(name=sites[1]),
            Layout(name=sites[2])
        )
        self.layout["col2"].split_column(
            Layout(name=sites[3]),
            Layout(name=sites[4])
        )

    def update_log(self, site: str, message: str):
        """Adds a new log message to a specific site's panel."""
        if site in self.logs:
            self.logs[site].append(message)
            if len(self.logs[site]) > 5: # Keep it short for the UI
                self.logs[site].pop(0)

    def update_status(self, site: str, status: str, progress: float = None):
        """Updates the status and progress for a site."""
        if site in self.status_data:
            self.status_data[site] = status
        if progress is not None and site in self.progress_data:
            self.progress_data[site] = progress

    def generate_layout(self) -> Layout:
        # Header
        self.layout["header"].update(Panel(Text("🚀 MARKETPULSE HARDCORE MONITOR", justify="center", style="bold magenta")))
        
        # Footer
        self.layout["footer"].update(Panel(Text("System Status: Active | Multi-Threading Mode", justify="center", style="dim")))
        
        # Site Panels
        for site in self.sites:
            log_text = "\n".join(self.logs[site])
            status = self.status_data[site]
            progress = self.progress_data[site]
            
            # Simple progress bar as text
            bar_len = 10
            filled = int(bar_len * (progress / 100))
            bar = "█" * filled + "░" * (bar_len - filled)
            
            panel_content = f"[bold cyan]Status:[/bold cyan] {status}\n[bold yellow]Progress:[/bold yellow] [{bar}] {progress}%\n\n{log_text}"
            self.layout[site].update(Panel(panel_content, title=f" {site} ", border_style="blue"))
            
        return self.layout

dashboard = None

def init_dashboard(sites: List[str]):
    global dashboard
    dashboard = DashboardManager(sites)
    return dashboard

def get_dashboard():
    return dashboard
