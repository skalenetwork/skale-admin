import React from 'react'
import {Link} from 'react-router-dom'

import {Icon} from 'rmwc/Icon';
import {
  Toolbar,
  ToolbarRow,
  ToolbarSection,
  ToolbarTitle,
  ToolbarMenuIcon,
  ToolbarIcon
} from 'rmwc/Toolbar';

import logo from '../../images/logos/logo-gr.jpg';


export default class Header extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      walletConnector: {},
    };
  }

  componentWillReceiveProps() {
    if (this.props.walletConnector) {
      this.setState({walletConnector: this.props.walletConnector})
    }
  }

  render() {
    return (
      <Toolbar className="skale-header">
        <ToolbarRow>
          <ToolbarSection alignStart>
            <ToolbarTitle className="no-padd no-marg">
              <Link to='/' className="undec">
                <img src={logo} className="header-logo"/>
              </Link>
            </ToolbarTitle>
          </ToolbarSection>
          <ToolbarSection alignEnd>

            <div className="fl-cont fl-center-vert">
              <div className="fl-wrap gx-icon marg-ri-md">
                <Icon strategy="ligature" className="gray-icon">help</Icon>

              </div>

              {/*<div className="fl-wrap marg-ri-10 marg-left-10">
                {this.props.avatarData ? <img width={35} height={35} style={{borderRadius: "10px"}}
                                              src={"data:image/png;base64," + this.props.avatarData}/> : null}
              </div>*/}
            </div>


          </ToolbarSection>
        </ToolbarRow>
      </Toolbar>
    );
  }
}
