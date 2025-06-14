# Discord Ship Tracking Bot - Development Prompt

## Objective
Create a Discord bot that automatically tracks a specific ship using maritime data APIs and posts location updates to a Discord channel every 2 days.

## Core Requirements

### Functionality
* **Automatic Scheduling**: Post ship location updates every 2 days
* **Real-time Data**: Fetch current ship position, speed, course, and destination
* **Discord Integration**: Send formatted messages with embedded rich content
* **Manual Override**: Include command to trigger immediate updates
* **Error Handling**: Gracefully handle API failures and network issues

### Technical Specifications
* **Language**: Python (preferred) or JavaScript/Node.js
* **APIs**: MarineTraffic API or suitable alternative (AISHub, VesselFinder)
* **Discord Library**: discord.py (Python) or discord.js (JavaScript)
* **Scheduling**: Built-in task scheduling (asyncio tasks or cron jobs)
* **Configuration**: Environment variables for secure credential storage

### Data Sources
* **Primary**: Web scraping from maritime tracking websites

## Message Format

### Rich Embeds
Use Discord embed format for attractive presentation with:

### Essential Info
* Ship name
* Current position (lat/lon)
* Speed and course
* Vessel status

### Additional Details
* Destination and ETA
* Last update timestamp
* Next scheduled update time

### Interactive Elements
* Google Maps link for location visualization
* Clickable links to tracking websites

### Example Output Format
```
🚢 **[Ship Name]** - My Best Friend Ship
📍 Position: 40.7128°N, 74.0060°W
⚡ Speed: 12.5 knots, Course: 045°
🎯 Destination: Port of New York
⏰ ETA: 2025-06-16 14:30 UTC
🗺️ [View on Map](https://maps.google.com/?q=40.7128,-74.0060)
```

## Commands

### Bot Commands
* `!ship` - Manual ship location request
* `!status` - Bot health check and next update time
* `!test` - API connection verification
* `!stop` - Stop automatic updates
* `!start` - Resume automatic updates

### Administrative Commands
* `!reset` - Reset counters or cached data
* `!config` - Show current configuration (non-sensitive)

## Security & Best Practices

### Environment Variables
* Store API keys and tokens securely
* Never hardcode sensitive information
* Use .env files for local development

### Error Handling
* Implement proper error logging
* Add rate limiting to prevent API abuse
* Handle network timeouts and retries
* Validate API responses before processing
* Graceful degradation when services are unavailable

### Logging
* Comprehensive logging for debugging
* Separate log files for different components
* Log rotation to prevent disk space issues

## Setup Requirements

### Discord Bot Setup
1. Discord bot creation and token generation
2. Bot permissions configuration
3. Server invitation and role setup
4. Channel ID identification for message posting

### Ship Information
1. Ship identification (MMSI or IMO number)
2. Verification of ship visibility on tracking platforms
3. Ship name and basic details

### API Configuration
1. API key acquisition from chosen maritime data provider
2. Rate limiting configuration
3. Backup API sources configuration

## Implementation Architecture

### Core Components
1. **Bot Client**: Discord.py bot instance with command handling
2. **Ship Tracker**: Data fetching and processing module
3. **Scheduler**: Background task management
4. **Data Formatter**: Message and embed creation
5. **Error Handler**: Logging and fallback mechanisms

### Data Flow
1. Scheduled task triggers every 2 days
2. Fetch ship data from primary source
3. Validate and process data
4. Create formatted Discord embed
5. Send message to configured channel
6. Log success/failure and update cache

### Error Recovery
1. Retry failed requests with exponential backoff
2. Use cached data when live data unavailable
3. Alert administrators of persistent failures
4. Graceful degradation of service features

## Optional Enhancements

### Advanced Features
* Multiple ship tracking capability
* Historical position tracking and visualization
* Weather data integration at ship location
* Port arrival/departure notifications
* Geofencing alerts for specific areas

### User Interface
* Web dashboard for configuration
* Mobile-friendly status page
* Interactive map integration
* Historical data charts and graphs

### Notifications
* Custom update frequency per ship
* Alert thresholds for unusual behavior
* Integration with other notification services
* Emergency contact systems

## Success Criteria

### Core Functionality
* Bot successfully authenticates with Discord
* Scheduled messages post every 2 days without manual intervention
* Ship data is accurate and current
* Error conditions are handled gracefully
* Manual commands work reliably

### Code Quality
* Code is maintainable and well-documented
* Proper separation of concerns
* Comprehensive error handling
* Secure handling of credentials
* Efficient resource usage

### User Experience
* Clear, informative message formatting
* Responsive manual commands
* Helpful error messages
* Intuitive command structure

## Deliverables

### Code Components
1. **Complete bot source code** with comprehensive comments
2. **Requirements/dependencies list** with version specifications
3. **Configuration files** and templates
4. **Database schema** (if applicable)

### Documentation
1. **Setup instructions** with step-by-step guide
2. **Environment variable configuration** template
3. **API documentation** and usage examples
4. **Troubleshooting guide** with common issues

### Deployment
1. **Docker configuration** for containerized deployment
2. **Systemd service files** for Linux deployment
3. **Process manager configuration** (PM2, supervisor)
4. **Backup and recovery procedures**

## Testing Requirements

### Unit Tests
* Individual function testing
* Mock API responses
* Error condition simulation

### Integration Tests
* End-to-end workflow testing
* Discord API integration
* Data source connectivity

### Load Testing
* Rate limiting verification
* Memory usage monitoring
* Long-running stability tests

## Monitoring and Maintenance

### Health Checks
* Bot uptime monitoring
* API response time tracking
* Error rate monitoring
* Resource usage alerts

### Maintenance Tasks
* Regular dependency updates
* Log file rotation and cleanup
* Performance optimization
* Security audit procedures

## Legal and Compliance

### Data Usage
* Respect website terms of service
* Implement proper rate limiting
* Consider data retention policies
* Comply with maritime data regulations

### Privacy
* Minimize data collection
* Secure data transmission
* Regular security updates
* User privacy protection

## Development Timeline

### Phase 1: Core Functionality (Week 1-2)
* Basic Discord bot setup
* Simple ship data fetching
* Manual command implementation
* Basic error handling

### Phase 2: Automation (Week 2-3)
* Scheduled task implementation
* Rich embed formatting
* Enhanced error handling
* Configuration management

### Phase 3: Polish (Week 3-4)
* Comprehensive testing
* Documentation completion
* Deployment preparation
* Performance optimization

### Phase 4: Deployment (Week 4)
* Production deployment
* Monitoring setup
* User training
* Maintenance procedures

This prompt provides a comprehensive foundation for developing a robust, production-ready Discord ship tracking bot with all necessary features, security considerations, and deployment requirements.