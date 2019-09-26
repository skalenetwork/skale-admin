import React from 'react'
import {Icon} from 'rmwc/Icon';

import {Collapse} from 'reactstrap';
import ReactJson from 'react-json-view'
import {LinearProgress} from 'rmwc/LinearProgress';
import {Tooltip} from 'reactstrap';

import {FlexCol, FlexCont} from "./shared_components/Flex";
import ContainerIcon from "./shared_components/ContainerIcon";

export default class Container extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      collapse: false,
      collapseConfig: false,
      tooltipOpen: false,
      configTooltipOpen: false
    };
    this.toggle = this.toggle.bind(this);
    this.toggleConfig = this.toggleConfig.bind(this);
    this.toggleTooltip = this.toggleTooltip.bind(this);
    this.toggleConfigTooltip = this.toggleConfigTooltip.bind(this);
  }

  toggle() {
    this.setState({collapse: !this.state.collapse});
  }

  toggleConfig() {
    this.getSChainConfig(this.props.dockerInfo.schain_name);
    this.setState({collapseConfig: !this.state.collapseConfig});
  }

  toggleTooltip() {
    this.setState({
      tooltipOpen: !this.state.tooltipOpen
    });
  }

  toggleConfigTooltip() {
    this.setState({
      configTooltipOpen: !this.state.configTooltipOpen
    });
  }


  getSChainConfig(schain_name) {
    let param_name = '?schain-name=';
    let base_url = '/schain-config';
    let url = base_url + param_name + schain_name;

    let self = this;
    fetch(url)
      .then((resp) => resp.json())
      .then(function (data) {
        self.setState({
          schainConfig: data.data
        });
      })
      .catch(function (error) {
        console.log(error);
      });
  }

  render() {

    console.log(`schains ${this.props.darkMode}`);

    return (
      <div className="sk-list-item padd-top-10 padd-bott-10">
        <FlexCont className="fl-center-h">
          <FlexCol>
            <ContainerIcon status={this.props.dockerInfo.info.status}/>
          </FlexCol>
          <FlexCol className="padd-left-md fl-grow">
            <h6 className="no-tmarg" style={{marginBottom: '3px'}}> {this.props.dockerInfo.name} </h6>
            <FlexCont>
              <FlexCol>
                <p className="no-marg fs-2 g-4 fw-5 marg-ri-10">v.{this.props.dockerInfo.image_version}  </p>
              </FlexCol>
              <FlexCol>
                <p className="no-marg fs-2 g-4 fw-5">|</p>
              </FlexCol>
              <FlexCol>
                <p className="no-marg fs-2 g-4 fw-5 marg-left-10 capitalize"> {this.props.dockerInfo.info.status} </p>
              </FlexCol>

              <FlexCol>
                <p className="padd-left-10 no-marg fs-2 g-4 fw-5">|</p>
              </FlexCol>

              <FlexCol>
                <p className="no-marg fs-2 g-4 fw-5 marg-left-10"> Health check: {this.props.dockerInfo.healthcheck_name} </p>
              </FlexCol>
            </FlexCont>


          </FlexCol>
          <FlexCol className="padd-left-md fl-center-h">
            <div onClick={this.toggle} className='hand-cursor md-icon'>
              <Icon id={"infoTooltip_" + this.props.dockerInfo.schain_name} strategy="ligature"
                    className={"md-icon " + (this.state.collapse ? 'icon-active' : 'accent-icon')}>info</Icon>
            </div>
            <Tooltip placement="left" isOpen={this.state.tooltipOpen}
                     target={"infoTooltip_" + this.props.dockerInfo.schain_name}
                     toggle={this.toggleTooltip}>
              sChain container statistics

            </Tooltip>
          </FlexCol>

          {/*<FlexCol className="padd-left-md fl-center-h">
                        <div onClick={this.toggle} className='hand-cursor md-icon'>
                            <Icon strategy="ligature"
                                  className="md-icon accent-icon">{this.state.collapse ? 'developer_board' : 'developer_board'} </Icon>
                        </div>
                    </FlexCol>*/}

          <FlexCol className="padd-left-md fl-center-h">
            <div onClick={this.toggleConfig} className='hand-cursor md-icon'>
              <Icon id={"configTooltip_" + this.props.dockerInfo.schain_name} strategy="ligature"
                    className={"md-icon " + (this.state.collapseConfig ? 'icon-active' : 'accent-icon')}>settings</Icon>
            </div>
            <Tooltip placement="left" isOpen={this.state.configTooltipOpen}
                     target={"configTooltip_" + this.props.dockerInfo.schain_name}
                     toggle={this.toggleConfigTooltip}>
              sChain configuration
            </Tooltip>
          </FlexCol>
        </FlexCont>

        <Collapse isOpen={this.state.collapse}>
          <div className='padd-top-md padd-left-md'>
            <ReactJson src={this.props.dockerInfo.info.stats} theme={this.props.darkMode ? 'hopscotch' : 'rjv-default'} style={{backgroundColor: 'transparent'}}/>
          </div>
        </Collapse>

        <Collapse isOpen={this.state.collapseConfig}>
          <div className='padd-top-md padd-left-md'>
            {this.state.schainConfig ? <ReactJson src={this.state.schainConfig} theme={this.props.darkMode ? 'hopscotch' : 'rjv-default'} style={{backgroundColor: 'transparent'}}/> :
              <LinearProgress determinate={false}></LinearProgress>}
          </div>
        </Collapse>

      </div>
    );
  }
}
