import React from 'react'
import {Link, withRouter} from 'react-router-dom'

import {Switch} from 'rmwc/Switch';
import {Icon} from 'rmwc/Icon';
import {
  Drawer,
  DrawerHeader,
  DrawerContent
} from 'rmwc/Drawer';

import {
  ListItem,
  ListItemText
} from 'rmwc/List';

import {Tooltip} from 'reactstrap';

import logoWhite from '../../images/logos/Skale_Logo_White.png';
import logoBlack from '../../images/logos/Skale_Logo_Black.png';

import SkaleAccount from '../components/SkaleAccount'

class Sidebar extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      persistentOpen: true,
      darkModeTooltip: false
    };
    this.toggleSidebar = this.toggleSidebar.bind(this);
    this.toggleDarkModeTooltip = this.toggleDarkModeTooltip.bind(this);
    this.toggleAboutTooltip = this.toggleAboutTooltip.bind(this);
    this.toggleAccountTooltip = this.toggleAccountTooltip.bind(this);
  }

  toggleDarkModeTooltip() {
    this.setState({
      darkModeTooltip: !this.state.darkModeTooltip
    });
  }

  toggleAboutTooltip() {
    this.setState({
      aboutTooltip: !this.state.aboutTooltip
    });
  }

  toggleAccountTooltip() {
    this.setState({
      accountTooltip: !this.state.accountTooltip
    });
  }

  toggleSidebar() {
    this.setState({persistentOpen: !this.state.persistentOpen})
  }

  isItemSelected(url) {
    return window.location.hash === '#' + url;
  }

  nodePage() {
    return this.isItemSelected('/create-node') || this.isItemSelected('/') || this.isItemSelected('/node')
  }

  miningPage() {
    return this.isItemSelected('mining')
  }

  slaPage() {
    return this.isItemSelected('/sla-bounty')
  }

  render() {
    return (
      <Drawer className="sidebar" persistent open={this.state.persistentOpen}>
        <DrawerContent>
          <div className="fl-cont fl-center-h padd-bott-30 padd-top-10">
            <div className="fl-col fl-grow" style={{padding: "20px 0 0 20px"}}>
              <Link to='/' className="undec">
                <img src={this.props.darkMode ? logoWhite : logoBlack} className="header-logo"/>
              </Link>
            </div>
          </div>

          <div className={"menu-items " + (this.props.hideMenu ? 'hidden' : '')}>
            <h5 className="sidebar-title">
              Validation
            </h5>

            <Link to='/' className="undec">
              <ListItem
                className={"fl-cont fl-center-vert sidebar-item " + (this.nodePage() ? 'selected-item' : '')}>
                <div className="fl-wrap gx-icon padd-left-10">
                  <Icon strategy="ligature" className="gray-icon">memory</Icon>
                </div>
                <ListItemText className="fl-wrap padd-left-md">
                  Dashboard
                </ListItemText>
              </ListItem>
            </Link>

            <Link to='/mining' className="undec">
              <ListItem
                className={"fl-cont fl-center-vert sidebar-item " + (this.isItemSelected('/mining') ? 'selected-item' : '')}>
                <div className="fl-wrap gx-icon padd-left-10">
                  <Icon strategy="ligature" className="gray-icon">widgets</Icon>
                </div>
                <ListItemText className="fl-wrap padd-left-md">
                  Mining
                </ListItemText>
              </ListItem>
            </Link>

            <Link to='/logs' className="undec">
              <ListItem
                className={"fl-cont fl-center-vert sidebar-item " + (this.isItemSelected('/logs') ? 'selected-item' : '')}>
                <div className="fl-wrap gx-icon padd-left-10">
                  <Icon strategy="ligature" className="gray-icon">assignment</Icon>
                </div>
                <ListItemText className="fl-wrap padd-left-md">
                  Logs
                </ListItemText>
              </ListItem>
            </Link>

            <Link to='/security' className="undec">
              <ListItem
                className={"fl-cont fl-center-vert sidebar-item " + (this.isItemSelected('/security') || this.isItemSelected('/add-certificate') ? 'selected-item' : '')}>
                <div className="fl-wrap gx-icon padd-left-10">
                  <Icon strategy="ligature" className="gray-icon">security</Icon>
                </div>
                <ListItemText className="fl-wrap padd-left-md">
                  Security
                </ListItemText>
              </ListItem>
            </Link>

            <Link to='/sla-bounty' className="undec">
              <ListItem
                className={"fl-cont fl-center-vert sidebar-item " + (this.slaPage() ? 'selected-item' : '')}>
                <div className="fl-wrap gx-icon padd-left-10">
                  <Icon strategy="ligature" className="gray-icon">table_chart</Icon>
                </div>
                <ListItemText className="fl-wrap padd-left-md">
                  SLA/Bounty
                </ListItemText>
              </ListItem>
            </Link>

            <h5 className="sidebar-title bord-top padd-top-md marg-top-md">
              Admin
            </h5>

            <Link to='/schains' className="undec">
              <ListItem
                className={"fl-cont fl-center-vert sidebar-item " + (this.isItemSelected('/schains') ? 'selected-item' : '')}>
                <div className="fl-wrap gx-icon padd-left-10">
                  <Icon strategy="ligature" className="gray-icon">offline_bolt</Icon>
                </div>
                <ListItemText className="fl-wrap padd-left-md">
                  sChains
                </ListItemText>
              </ListItem>
            </Link>
          </div>


          <div style={{position: "fixed", bottom: 0, padding: '20px'}}>
            <div className="fl-cont">
              <div className='fl-col fl-grow'>
                <div className="fl-cont fl-center-h" id='darkModeTooltip'>
                  <div className="fl-col padd-ri-10">
                    <Icon strategy="ligature" className="gray-icon"
                          style={{marginTop: '2px'}}>brightness_4</Icon>
                  </div>
                  <div className="fl-col">
                    <Switch
                      checked={!!this.props.darkMode}
                      onChange={evt => this.props.setDarkMode(evt.target.checked)}>
                    </Switch>
                  </div>
                </div>
                <Tooltip placement="left" isOpen={this.state.darkModeTooltip}
                         target="darkModeTooltip"
                         toggle={this.toggleDarkModeTooltip}>
                  Dark mode
                </Tooltip>
              </div>

              <div style={{paddingLeft: '70px'}}>
                <SkaleAccount setMenuVisibility={this.props.setMenuVisibility}>
                  <div className='fl-col undec marg-ri-10'>
                    <Icon id="accountTooltip" strategy="ligature"
                          className="accent-icon hand-cursor"
                          style={{marginTop: '2px'}}>account_circle</Icon>
                    <Tooltip placement="left" isOpen={this.state.accountTooltip}
                             target="accountTooltip"
                             toggle={this.toggleAccountTooltip}>
                      Account
                    </Tooltip>
                  </div>
                </SkaleAccount>
              </div>

              <Link to="/about" className='fl-col undec padd-left-md'>
                <Icon id="aboutTooltip" strategy="ligature" className="accent-icon"
                      style={{marginTop: '2px'}}>info</Icon>
                <Tooltip placement="left" isOpen={this.state.aboutTooltip}
                         target="aboutTooltip"
                         toggle={this.toggleAboutTooltip}>
                  About
                </Tooltip>
              </Link>
            </div>

          </div>


        </DrawerContent>
      </Drawer>
    )
  }
}

export default withRouter(Sidebar);




