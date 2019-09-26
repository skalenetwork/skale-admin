import React from 'react'
import {Link} from 'react-router-dom'

import {Icon} from 'rmwc/Icon';

import {Collapse} from 'reactstrap';
import ReactJson from 'react-json-view'
import {LinearProgress} from 'rmwc/LinearProgress';
import {Tooltip} from 'reactstrap';

import {FlexCol, FlexCont} from "./shared_components/Flex";
import ContainerIcon from "./shared_components/ContainerIcon";
import SkMdIcon from "./shared_components/SkMdIcon";


export default class Log extends React.Component {

  constructor(props) {
    super(props);
    this.state = {};

    this.toggle = this.toggle.bind(this);
    this.toggleTooltip = this.toggleTooltip.bind(this);
  }

  // todo: move it
  formatBytes(a,b){if(0==a)return"0 Bytes";var c=1024,d=b||2,e=["Bytes","KB","MB","GB","TB","PB","EB","ZB","YB"],f=Math.floor(Math.log(a)/Math.log(c));return parseFloat((a/Math.pow(c,f)).toFixed(d))+" "+e[f]}


  formatTimestamp(timestamp){
    let  date = new Date(timestamp*1000);
    return date.toISOString()
  }

  formatDate(date) {
    var d = new Date(date),
        month = '' + (d.getMonth() + 1),
        day = '' + d.getDate(),
        year = d.getFullYear();

    if (month.length < 2) month = '0' + month;
    if (day.length < 2) day = '0' + day;

    return [year, month, day].join('-');
}


  logIconClass(value) {
    switch (value) {
      case 'schain':
        return 'lite-green-icon';
      case 'base':
        return 'orange-icon';
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
      <div className="sk-list-item padd-top-10 padd-bott-10">
        <FlexCont className="fl-center-h">
          <FlexCol>
            <SkMdIcon icon='description' class={this.logIconClass(this.props.log.type)}/>
          </FlexCol>
          <FlexCol className="padd-left-md fl-grow">
            <h5 className="no-tmarg fw-6 fs-4" style={{marginBottom: '3px'}}> {this.props.log.name} </h5>
            <FlexCont>
              <FlexCol>
                <p className="no-marg fs-2 g-4 fw-5 marg-ri-10"> Size: {this.formatBytes(this.props.log.size)}  </p>
              </FlexCol>
              <FlexCol>
                <p className="no-marg fs-2 g-4 fw-5">|</p>
              </FlexCol>
              <FlexCol>
                <p
                  className="no-marg fs-2 g-4 fw-5 marg-left-10"> Last modification: {this.formatTimestamp(this.props.log.created_at)} </p>
              </FlexCol>
            </FlexCont>
          </FlexCol>

          <FlexCol className="padd-left-md fl-center-h">


            <a href={this.props.log.download_url} className='undec'>
              <div className='hand-cursor md-icon'>
                <Icon id={"infoTooltip_" + this.props.log.name} strategy="ligature"
                      className={"md-icon " + (this.state.collapse ? 'icon-active' : 'accent-icon')}>get_app</Icon>
              </div>
            </a>

            {/*<Tooltip placement="left" isOpen={this.state.tooltipOpen}
                     target={"infoTooltip_" + this.props.log.name}
                     toggle={this.toggleTooltip}>
              Download file
            </Tooltip>*/}
          </FlexCol>
        </FlexCont>

        {/*<Collapse isOpen={this.state.collapse}>
            <div className='padd-top-md padd-left-md'>
              <ReactJson src={this.props.schain.nodes}
                         theme={this.props.darkMode ? 'hopscotch' : 'rjv-default'}
                         style={{backgroundColor: 'transparent'}}/>
            </div>
          </Collapse>*/}

      </div>
    );
  }
}
