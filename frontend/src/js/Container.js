import React from 'react'
import {Icon} from 'rmwc/Icon';

import {Collapse, Tooltip} from 'reactstrap';
import ReactJson from 'react-json-view'

import {FlexCol, FlexCont} from "./shared_components/Flex";
import ContainerIcon from "./shared_components/ContainerIcon";

export default class Container extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            collapse: false,
            tooltipOpen: false
        };
        this.toggle = this.toggle.bind(this);
        this.toggleTooltip = this.toggleTooltip.bind(this);

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
                        <ContainerIcon status={this.props.container.info.status}/>
                    </FlexCol>
                    <FlexCol className="padd-left-md fl-grow">
                        <h6 className="no-tmarg" style={{marginBottom: '3px'}}> {this.props.container.name} </h6>
                        <FlexCont>
                            <FlexCol>
                                <p className="no-marg fs-2 g-4 fw-5 marg-ri-10">v.{this.props.container.image_version}  </p>
                            </FlexCol>
                            <FlexCol>
                                <p className="no-marg fs-2 g-4 fw-5">|</p>
                            </FlexCol>
                            <FlexCol>
                                <p className="no-marg fs-2 g-4 fw-5 marg-left-10 capitalize"> {this.props.container.info.status} </p>
                            </FlexCol>
                        </FlexCont>


                    </FlexCol>

                    {/*<FlexCol className="padd-left-md fl-center-h">
                        <div onClick={this.toggle} className='hand-cursor md-icon'>
                            <Icon strategy="ligature"
                                  className="md-icon accent-icon">{this.state.collapse ? 'keyboard_arrow_up' : 'keyboard_arrow_down'} </Icon>
                            <Icon strategy="ligature" className="sm-icon accent-icon">info</Icon>
                        </div>
                    </FlexCol>*/}

                    <FlexCol className="padd-left-md fl-center-h">
                        <div onClick={this.toggle} className='hand-cursor md-icon'>
                            <Icon id={"infoTooltip_" + this.props.container.name} strategy="ligature"
                                  className={"md-icon " + (this.state.collapse ? 'icon-active' : 'accent-icon')}>info</Icon>
                        </div>
                        <Tooltip placement="left" isOpen={this.state.tooltipOpen}
                                 target={"infoTooltip_" + this.props.container.name}
                                 toggle={this.toggleTooltip}>
                            Container statistics
                        </Tooltip>
                    </FlexCol>


                </FlexCont>

                <Collapse isOpen={this.state.collapse}>
                    <div className='padd-top-md padd-left-md'>
                        <ReactJson src={this.props.container.info.stats} theme={this.props.darkMode ? 'hopscotch' : 'rjv-default'} style={{backgroundColor: 'transparent'}}/>

                    </div>
                </Collapse>

            </div>
        );
    }
}
