import React from 'react'
import {Icon} from 'rmwc/Icon';

import {Collapse} from 'reactstrap';
import ReactJson from 'react-json-view'
import {LinearProgress} from 'rmwc/LinearProgress';
import {Tooltip} from 'reactstrap';

import {FlexCol, FlexCont} from "./shared_components/Flex";
import ContainerIcon from "./shared_components/ContainerIcon";
import SchainIcon from "./shared_components/SchainIcon";


export default class Container extends React.Component {

  constructor(props) {
    super(props);
    this.state = {};

    this.toggle = this.toggle.bind(this);
    this.toggleTooltip = this.toggleTooltip.bind(this);
  }


  schainTypeName(value) {
    switch (value) {
      case 0:
        return 'test';
      case 1:
        return 'medium';
      case 8:
        return 'small';
      case 128:
        return 'tiny';
      default:
        return 'unknown';
    }
  }

  toggle() {
    this.setState({collapse: !this.state.collapse});
  }


  toggleTooltip() {
    this.setState({
      tooltipOpen: !this.state.tooltipOpen
    });
  }

  render() {
    return (
      <div className="sk-list-item padd-top-15 padd-bott-15">
        <FlexCont className="fl-center-h">
          <FlexCol>
            <SchainIcon status={this.schainTypeName(this.props.schain.partOfNode)}/>
            {/*<ContainerIcon status='running'/>*/}
          </FlexCol>
          <FlexCol className="padd-left-md fl-grow">
            <h5 className="no-tmarg fw-6" style={{marginBottom: '3px'}}> {this.props.schain.name} </h5>
            <FlexCont>
              <FlexCol>
                <p className="no-marg fs-2 g-4 fw-5 marg-ri-10"> Owner: {this.props.schain.owner}  </p>
              </FlexCol>
              <FlexCol>
                <p className="no-marg fs-2 g-4 fw-5">|</p>
              </FlexCol>
              <FlexCol>
                <p
                  className="no-marg fs-2 g-4 fw-5 marg-left-10"> Type: {this.schainTypeName(this.props.schain.partOfNode)} </p>
              </FlexCol>
            </FlexCont>
          </FlexCol>

          <FlexCol className="padd-left-md fl-center-h">
            <div onClick={this.toggle} className='hand-cursor md-icon'>
              <Icon id={"infoTooltip_" + this.props.schain.name} strategy="ligature"
                    className={"md-icon " + (this.state.collapse ? 'icon-active' : 'accent-icon')}>info</Icon>
            </div>
            <Tooltip placement="left" isOpen={this.state.tooltipOpen}
                     target={"infoTooltip_" + this.props.schain.name}
                     toggle={this.toggleTooltip}>
              sChain info
            </Tooltip>
          </FlexCol>



          {/*<FlexCol className="padd-left-md fl-center-h">
                        <div onClick={this.toggle} className='hand-cursor md-icon'>
                            <Icon strategy="ligature"
                                  className="md-icon accent-icon">{this.state.collapse ? 'developer_board' : 'developer_board'} </Icon>
                        </div>
                    </FlexCol>*/}

          {/*<FlexCol className="padd-left-md fl-center-h">
            <div onClick={this.toggleConfig} className='hand-cursor md-icon'>
              <Icon id={"configTooltip_" + this.props.dockerInfo.schain_name} strategy="ligature"
                    className={"md-icon " + (this.state.collapseConfig ? 'icon-active' : 'accent-icon')}>settings</Icon>
            </div>
            <Tooltip placement="left" isOpen={this.state.configTooltipOpen}
                     target={"configTooltip_" + this.props.dockerInfo.schain_name}
                     toggle={this.toggleConfigTooltip}>
              sChain configuration
            </Tooltip>
          </FlexCol>*/}
        </FlexCont>

        <Collapse isOpen={this.state.collapse}>
            <div className='padd-top-md padd-left-md'>
              <ReactJson src={this.props.schain.nodes}
                         theme={this.props.darkMode ? 'hopscotch' : 'rjv-default'}
                         style={{backgroundColor: 'transparent'}}/>
            </div>
          </Collapse>

      </div>
    );
  }
}
